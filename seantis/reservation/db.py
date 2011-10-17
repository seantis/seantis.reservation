from uuid import uuid4 as uuid
from uuid import uuid5 as uuid_mirror

from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.error import AlreadyReservedError
from seantis.reservation.lock import locked_call
from seantis.reservation.raster import rasterize_span

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
        ),
    )

class Scheduler(object):
    """ Used to manage a resource as well as all connected mirrors. """

    def __init__(self, resource_uuid, quota=1):
        assert(0 <= quota)

        self.master = ResourceScheduler(resource_uuid)
        self.mirrors = []

        # get a scheduler for each mirror
        if quota > 1:
            scheduler = lambda uid: ResourceScheduler(uid)
            mirror = lambda n: scheduler(uuid_mirror(self.master.uuid, str(n)))

            self.mirrors = [mirror(n) for n in xrange(1, quota)]

        self.schedulers = [self.master]
        self.schedulers.extend(self.mirrors)

    def execute_master(self, method, *args, **kwargs):
        """ Execute a method on the master. """
        fn = getattr(self.master, method)
        return fn(*args, **kwargs)

    def execute_mirrors(self, method, *args, **kwargs):
        """ Execute a method on all mirrors. """
        for mirror in self.mirrors:
            fn = getattr(mirror, method)
            fn(*args, **kwargs)

    def execute_all(self, method, *args, **kwargs):
        """ Execute a method on all mirrors as well as the master."""
        result = self.execute_master(method, *args, **kwargs)
        self.execute_mirrors(method, *args, **kwargs)
        return result

    def __getattr__(self, name):
        """ Called when a method or argument is not found on this class. In that
        case the scheduler tries to call the master resource scheduler and 
        optionally the mirrors.

        The call may be wrapped in a resource lock.

        The decision to wrap or execute many calls is made based upon the
        flags which are set by the decorators below.

        Only callables are considered.

        """
        attr = getattr(self.master, name)

        if not callable(attr):
            return attr

        mirrored = hasattr(attr, '_mirrored')
        locked = hasattr(attr, '_locked')

        execute = mirrored and self.execute_all or self.execute_master
        execute = locked and locked_call(execute, self.master.uuid) or execute

        def fn(*args, **kwargs):
            return execute(name, *args, **kwargs)

        return fn

    def reserve(self, dates):
        """ Tries to reserve a number of dates. If dates are found which are
        already reserved, an AlreadyReservedError is thrown. If a reservation
        is made between the availability check and the reservation an integrity
        error will surface once the session is flushed.

        """
        reservation = uuid()
        slots_to_reserve = []

        for start, end in dates:
            for allocation in self.reservation_targets(start, end):
                for slot_start, slot_end in allocation.all_slots(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.allocation = allocation
                    slot.resource = allocation.resource
                    slot.reservation = reservation

                    slots_to_reserve.append(slot)

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

        tries = master.quota - 1

        for mirror in self.mirrors:
            if tries == 0:
                return None

            next = mirror.get_allocation(start=master.start, end=master.end)
            if next.is_available(start, end):
                return next

            tries -= 1

        return None

    def reservation_targets(self, start, end):
        """ Returns a list of allocations that are free within start and end.
        These allocations may come from the master or any of the mirrors. 

        """
        targets = []

        candidates = self.master.allocations_in_range(start, end)
        for candidate in candidates:

            found = self.find_spot(candidate, start, end)
            
            if not found:
                raise AlreadyReservedError

            targets.append(found)

        return targets

    def managed_reserved_slots(self):
        """Returns the reserved slots which are managed by this scheduler."""
        resources = [sc.uuid for sc in self.schedulers]
        query = Session.query(ReservedSlot).filter(
                ReservedSlot.resource.in_(resources)
            )
        return query

    def reserved_slots(self, reservation):
        """Returns all reserved slots of the given reservation."""
        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.reservation == reservation)

        for result in query:
            yield result

    def remove_reservation(self, reservation):
        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.reservation == reservation)

        query.delete('fetch')

def mirrored(fn):
    """ Decorator to signal to the scheduler that the function should be executed
    on the master and all mirrors. 

    """
    fn._mirrored = True
    return fn

def mirrored_transaction(fn):
    """ Signals to the scheduler that the call shall be mirrored and executed
    within a resource transaction. 

    """
    fn._mirrored = True
    fn._locked = True
    return fn


class ResourceScheduler(object):
    """Used to manage the definitions and reservations of a resource."""

    def __init__(self, resource_uuid):
        self.uuid = resource_uuid

    @mirrored_transaction
    def allocate(self, dates, group=None, raster=15):
        group = group or unicode(uuid())

        # Make sure that this span does not overlap another
        for start, end in dates:
            start, end = rasterize_span(start, end, raster)
            existing = self.any_allocations_in_range(start, end)
            
            if existing:
                raise OverlappingAllocationError(start, end, existing)

        # Prepare the allocations
        allocations = []

        for start, end in dates:
            allocation = Allocation(raster=raster)
            allocation.start = start
            allocation.end = end
            allocation.group = group
            allocation.resource = self.uuid

            allocations.append(allocation)

        Session.add_all(allocations)

        return group, allocations

    @mirrored_transaction
    def move_allocation(self, id, new_start, new_end, group):
        # Find allocation
        allocation = self.get_allocation(id)

        # Simulate the new allocation
        new = Allocation(start=new_start, end=new_end, raster=allocation.raster)

        # Ensure that the new span does not overlap an existing one
        for existing in self.allocations_in_range(new.start, new.end):
            if existing.id != allocation.id:
                raise OverlappingAllocationError(new.start, new.end, existing)

        # Ensure that no existing reservation would be affected
        for reservation in allocation.reserved_slots:
            if not new.contains(reservation.start, reservation.end):
                raise AffectedReservationError(reservation)

        # Change the actual allocation
        allocation.start = new_start
        allocation.end = new_end
        allocation.group = group or unicode(uuid())

    def get_allocation(self, id=None, start=None, end=None):
        if id:
            return self.allocations(id=id).one()

        if start and end:
            return all_allocations_in_range(start, end).one()


    def get_allocations(self, group):
        return self.allocations(group=group).all()

    def allocations(self, id=None, group=None):
        if id:
            query = Session.query(Allocation).filter(and_(
                Allocation.id == id,
                Allocation.resource == self.uuid
            ))
        elif group:
            query = Session.query(Allocation).filter(and_(
                Allocation.group == group,
                Allocation.resource == self.uuid
            ))
        else:
            query = Session.query(Allocation).filter(
                Allocation.resource == self.uuid
            )

        return query

    @mirrored_transaction
    def remove_allocation(self, id=None, group=None):
        query = self.allocations(id=id, group=group)

        for allocation in query:
            if allocation.reserved_slots.count() > 0:
                raise AffectedReservationError(allocation.reserved_slots.first())

        query.delete()

    def any_allocations_in_range(self, start, end):
        """Returns the first allocated timespan in the range or None."""
        for allocation in self.allocations_in_range(start, end):
            return allocation

        return None

    def allocations_in_range(self, start, end):
        """Yields a list of allocations for the current resource."""
        
        query = all_allocations_in_range(start, end)
        query = query.filter(Allocation.resource == self.uuid)

        for result in query:
            yield result

    def availability(self, start=None, end=None):
        """Goes through all allocations and sums up the availabilty."""

        if all((start, end)):
            query = self.allocations_in_range(start, end)
        else:
            query = Session.query(Allocation)
            query = query.filter(Allocation.resource == self.uuid)

        count, availability = 0, 0.0
        for allocation in query:
            count += 1
            availability += allocation.availability
            
        if not count:
            return 0, 0.0

        return count, availability / float(count)

    def allocations_by_group(self, group):
        """Yields a list of all allocations with the given group."""

        query = Session.query(Allocation)
        query = query.filter(Allocation.resource == self.uuid)
        query = query.filter(Allocation.group == group)

        for result in query:
            yield result