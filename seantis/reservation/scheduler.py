from uuid import uuid4 as uuid
from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import Available
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import OverlappingAvailable

class Scheduler(object):
    """Used to manage the definitions and reservations of a resource."""

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    def make_available(self, dates, group=uuid(), raster=15):
        """Makes a list of dates available with the given group and raster. 
        Raises a OverlappingAvailable exception if any date conflicts with an 
        existing definition. 

        """

        # TODO add locking here (one resource - one scheduler)

        # Make sure that this span does not overlap another
        for start, end in dates:
            existing = self.any_available_in_range(start, end)
            
            if existing:
                raise OverlappingAvailable(start, end, existing)

        # Create the availabilities
        availables = []

        for start, end in dates:
            available = Available(raster=raster)
            available.start = start
            available.end = end
            available.group = group
            available.resource = self.resource

            availables.append(available)

        Session.add_all(availables)

        return group, availables

    def any_available_in_range(self, start, end):
        """Returns the first available timespan in the range or None."""
        for available in self.available_in_range(start, end):
            return available

        return None

    def available_in_range(self, start, end):
        """Yields a list of available timespans for the current resource."""
        
        # Query version of DefinedTimeSpan.overlaps
        query = Session.query(Available).filter(
            or_(
                and_(
                    Available._start <= start,
                    start <= Available._end
                ),
                and_(
                    start <= Available._start,
                    Available._start <= end
                )
            ),
        )

        query = query.filter(Available.resource == self.resource)

        for result in query:
            yield result

    def reserve(self, dates):
        """Tries to reserve a list of dates (tuples). If these dates are already
        reserved then the sqlalchemy commit/flash will fail.

        """
        reservation = uuid()
        slots_to_reserve = []

        for start, end in dates:
            for available in self.available_in_range(start, end):
                for slot_start, slot_end in available.all_slots(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.available = available
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

    def remove_definition(self, group):
        query = Session.query(Available).filter(
            Available.group == group
        )

        query.delete()