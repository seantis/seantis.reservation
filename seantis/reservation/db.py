from uuid import uuid4 as uuid
from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.lock import resource_transaction
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
    """Used to manage the definitions and reservations of a resource."""

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    @resource_transaction
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
            allocation.resource = self.resource

            allocations.append(allocation)

        Session.add_all(allocations)

        return group, allocations

    @resource_transaction
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

    def get_allocation(self, id):
        return self.allocations(id=id).one()

    def get_allocations(self, group):
        return self.allocations(group=group).all()

    def allocations(self, id=None, group=None):
        if id:
            query = Session.query(Allocation).filter(and_(
                Allocation.id == id,
                Allocation.resource == self.resource
            ))
        elif group:
            query = Session.query(Allocation).filter(and_(
                Allocation.group == group,
                Allocation.resource == self.resource
            ))
        else:
            query = Session.query(Allocation).filter(
                Allocation.resource == self.resource
            )

        return query

    @resource_transaction
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
        query = query.filter(Allocation.resource == self.resource)

        for result in query:
            yield result

    def availability(self, start=None, end=None):
        """Goes through all allocations and sums up the availabilty."""

        if all((start, end)):
            query = self.allocations_in_range(start, end)
        else:
            query = Session.query(Allocation)
            query = query.filter(Allocation.resource == self.resource)

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
        query = query.filter(Allocation.resource == self.resource)
        query = query.filter(Allocation.group == group)

        for result in query:
            yield result

    def reserve(self, dates):
        """Tries to reserve a list of dates (tuples). If these dates are already
        reserved then the sqlalchemy commit/flash will fail.

        """
        reservation = uuid()
        slots_to_reserve = []

        for start, end in dates:
            for allocation in self.allocations_in_range(start, end):
                for slot_start, slot_end in allocation.all_slots(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.allocation = allocation
                    slot.resource = self.resource
                    slot.reservation = reservation

                    slots_to_reserve.append(slot)
        
        Session.add_all(slots_to_reserve)

        return reservation, slots_to_reserve

    def reserved_slots(self, reservation):
        """Returns all reserved slots of the given reservation."""
        query = Session.query(ReservedSlot).filter(
                ReservedSlot.reservation == reservation
            )

        for result in query:
            yield result

    def remove_reservation(self, reservation):
        query = Session.query(ReservedSlot).filter(and_(
                ReservedSlot.reservation == reservation,
                ReservedSlot.resource == self.resource
            ))

        query.delete()