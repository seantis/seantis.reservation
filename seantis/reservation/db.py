from uuid import UUID
from uuid import uuid4 as new_uuid
from uuid import uuid5 as new_uuid_mirror
from datetime import date, datetime, MINYEAR, MAXYEAR
from itertools import chain

from sqlalchemy.sql import and_, or_

from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.error import AlreadyReservedError
from seantis.reservation.error import NotReservableError
from seantis.reservation.session import serialized
from seantis.reservation.raster import rasterize_span
from seantis.reservation import utils
from seantis.reservation import Session
    
def all_allocations_in_range(start, end):
    # Query version of DefinedTimeSpan.overlaps
    return Session.query(Allocation).filter(
        or_(
            and_(
                Allocation._start <= start,
                start <= Allocation._end
            ),
            and_(
                start <= Allocation._start,
                Allocation._start <= end
            )
        )
    )

class Scheduler(object):
    """ Used to manage a resource as well as all connected mirrors. 

    TODO: One thing about this class, it is less than optimal. If I assign a
    quota of 100 all records are written a hundred times independent of need.

    This should be revised, minimizing database interaction.
    """

    def __init__(self, resource_uuid, quota=1, masks=None):
        assert(0 <= quota)

        try: 
            self.uuid = UUID(resource_uuid)
        except AttributeError: 
            self.uuid = resource_uuid
        
        self.masks = masks
        self.mirrors = []
        self.quota = quota

        if self.quota > 1:
            mirror = lambda n: new_uuid_mirror(self.uuid, str(n))
            self.mirrors = [mirror(n) for n in xrange(1, quota)]

        self.uuids = [self.uuid]
        self.uuids.extend(self.mirrors)

    @serialized
    def allocate(self, dates, group=None, raster=15, quota=None, partly_available=False):
        dates = utils.pairs(dates)

        group = group or unicode(new_uuid())
        quota = quota or self.quota

        # Make sure that this span does not overlap another master
        for start, end in dates:
            start, end = rasterize_span(start, end, raster)
            
            query = all_allocations_in_range(start, end)
            query = query.filter(Allocation.resource == self.uuid)

            existing = query.first()
            if existing:
                raise OverlappingAllocationError(start, end, existing)
        
        # Write the master allocations
        allocations = []
        for start, end in dates:
            allocation = Allocation(raster=raster)
            allocation.start = start
            allocation.end = end
            allocation.group = group
            allocation.resource = self.uuid
            allocation.quota = quota
            allocation.mirror_of = self.uuid
            allocation.partly_available = partly_available
                
            allocations.append(allocation)

        Session.add_all(allocations)

        return group, allocations

    def allocation_by_id(self, id):
        query = Session.query(Allocation)
        query = query.filter(Allocation.resource == self.uuid)
        query = query.filter(Allocation.id == id)
        return query.one()

    def allocations_by_group(self, group):
        query = Session.query(Allocation)
        query = query.filter(Allocation.group == group)
        query = query.filter(Allocation.resource == self.uuid)
        return query

    def allocations_in_range(self, start, end):
        query = all_allocations_in_range(start, end)
        query = query.filter(Allocation.resource == self.uuid)
        return query

    def allocation_by_date(self, start, end):
        query = self.allocations_in_range(start, end)
        return query.one()

    def allocation_mirrors_by_master(self, master):
        if not self.mirrors: return []

        query = Session.query(Allocation)
        query = query.filter(Allocation.mirror_of == self.uuid)
        query = query.filter(Allocation.resource != self.uuid)
        
        existing = query.all()
        existing = dict([(e.resource, e) for e in existing])

        imaginary = master.quota - len(existing)
        
        mirrors = []
        for uuid in self.mirrors:
            if uuid in existing:
                mirrors.append(existing[uuid])
            elif imaginary:
                imaginary -= 1

                allocation = Allocation(resource=uuid)
                allocation.raster = master.raster
                allocation.start = master.start
                allocation.end = master.end
                allocation.group = master.group
                allocation.quota = master.quota
                allocation.mirror_of = master.mirror_of
                allocation.partly_available = master.partly_available

                allocation._imaginary = True
                mirrors.append(allocation)

        return mirrors

    def reservable(self, allocation):
        return self.render_allocation(allocation)

    def render_allocation(self, allocation):
        if not self.masks:
            return True

        start = allocation.start
        day = date(start.year, start.month, start.day)

        for mask in self.masks:
            if mask.start <= day and day <=mask.end:
                return mask.visible

        return False

    def availability(self, start=None, end=None):
        """Goes through all allocations and sums up the availabilty."""

        if not (start and end):
            start = datetime(MINYEAR, 1, 1)
            end = datetime(MAXYEAR, 12, 31)

        query = all_allocations_in_range(start, end)
        query = query.filter(Allocation.resource == Allocation.mirror_of)
        
        masters = query.all()
        mirrors = chain(*[self.allocation_mirrors_by_master(m) for m in masters])
       
        allocations = chain(masters, mirrors)

        count, availability = 0, 0.0
        for allocation in allocations:
            if self.render_allocation(allocation):
                count += 1
                availability += allocation.availability
            
        if not count:
            return 0, 0.0

        return count, availability

    @serialized
    def move_allocation(self, master_id, new_start, new_end, group):
        # Find allocation
        master = self.allocation_by_id(master_id)
        mirrors = self.allocation_mirrors_by_master(master)
        changing = [master] + mirrors
        ids = [c.id for c in changing]

        assert(group or master.group)

        # Simulate the new allocation
        new = Allocation(start=new_start, end=new_end, raster=master.raster)

        # Ensure that the new span does not overlap an existing one
        existing_allocations = self.allocations_in_range(new.start, new.end)

        for existing in existing_allocations:
            if existing.id not in ids:
                raise OverlappingAllocationError(new.start, new.end, existing)

        for change in changing:
            if change.partly_available:
                for reservation in change.reserved_slots:
                    if not new.contains(reservation.start, reservation.end):
                        raise AffectedReservationError(reservation)
            else:
                reservation = change.reserved_slots.first()
                if reservation:
                    raise AffectedReservationError(reservation)

        for change in changing:
            change.start = new.start
            change.end = new.end
            change.group = group or master.group

    @serialized
    def remove_allocation(self, id=None, group=None):
        if id:
            master = self.allocation_by_id(id)
            allocations = [master]
            allocations.extend(self.allocation_mirrors_by_master(master))
        elif group:
            query = Session.query(Allocation)
            query = query.filter(Allocation.group == group)
            query = query.filter(Allocation.resource.in_(self.uuids))
            allocations = query.all()
        else:
            raise NotImplementedError
        
        for allocation in allocations:
            if allocation.reserved_slots.count() > 0:
                raise AffectedReservationError(allocation.reserved_slots.first())

        for allocation in allocations:
            if not hasattr(allocation, '_imaginary'):
                Session.delete(allocation)

    @serialized
    def reserve(self, dates):
        """ Tries to reserve a number of dates. If dates are found which are
        already reserved, an AlreadyReservedError is thrown. If a reservation
        is made between the availability check and the reservation an integrity
        error will surface once the session is flushed.

        """
        dates = utils.pairs(dates)
        reservation = new_uuid()
        slots_to_reserve = []

        for start, end in dates:
            for allocation in self.reservation_targets(start, end):
                if not self.reservable(allocation):
                    continue

                if hasattr(allocation, '_imaginary'):
                    delattr(allocation, '_imaginary')
                    Session.add(allocation)

                for slot_start, slot_end in allocation.all_slots(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.allocation = allocation
                    slot.resource = allocation.resource
                    slot.reservation = reservation

                    slots_to_reserve.append(slot)

        if not slots_to_reserve:
            raise NotReservableError

        Session.add_all(slots_to_reserve)

        return reservation, slots_to_reserve

    def find_spot(self, master_allocation, start, end):
        """ Returns the first free allocation spot amongst the master and the
        mirrors. Honors the quota set on the master and will only try the master
        if the quota is set to 1.

        If no spot can be found, None is returned.

        """
        master = master_allocation
        if master.is_available(start, end):
            return master

        if master.quota == 1:
            return None
        
        mirrors = self.allocation_mirrors_by_master(master)
        tries = master.quota - 1

        for mirror in mirrors:
            if mirror.is_available(start, end):
                return mirror

            if tries >= 1:
                tries -= 1
            else:
                return None

    def reservation_targets(self, start, end):
        """ Returns a list of allocations that are free within start and end.
        These allocations may come from the master or any of the mirrors. 

        """
        targets = []

        query = all_allocations_in_range(start, end)
        query = query.filter(Allocation.resource == self.uuid)

        for master_allocation in query:
            if not master_allocation.overlaps(start, end):
                continue # may happen because start and end are not rasterized

            found = self.find_spot(master_allocation, start, end)
            
            if not found:
                raise AlreadyReservedError

            targets.append(found)

        return targets

    def managed_reserved_slots(self):
        """Returns the reserved slots which are managed by this scheduler."""
        query = Session.query(ReservedSlot).filter(
                ReservedSlot.resource.in_(self.uuids)
            )
        return query

    def reserved_slots(self, reservation):
        """Returns all reserved slots of the given reservation."""
        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.reservation == reservation)

        for result in query:
            yield result

    @serialized
    def remove_reservation(self, reservation):
        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.reservation == reservation)

        query.delete('fetch')