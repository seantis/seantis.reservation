from uuid import uuid4 as uuid
from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.lock import resource_transaction

class Scheduler(object):
    """Used to manage the definitions and reservations of a resource."""

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    @resource_transaction
    def allocate(self, dates, group=None, raster=15):
        group = group or uuid()

        # Make sure that this span does not overlap another
        for start, end in dates:
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

    def any_allocations_in_range(self, start, end):
        """Returns the first allocated timespan in the range or None."""
        for allocation in self.allocations_in_range(start, end):
            return allocation

        return None

    def allocations_in_range(self, start, end):
        """Yields a list of allocations for the current resource."""
        
        # Query version of DefinedTimeSpan.overlaps
        query = Session.query(Allocation).filter(
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

        query = query.filter(Allocation.resource == self.resource)

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
        query = Session.query(ReservedSlot).filter(
            ReservedSlot.reservation == reservation
        )

        query.delete()

    @resource_transaction
    def remove_allocation(self, group):
        query = Session.query(Allocation).filter(
            Allocation.group == group
        )

        query.delete()