from uuid import uuid4 as uuid
from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import DefinedTimeSpan
from seantis.reservation.models import ReservedSlot
from seantis.reservation.error import DefinitionConflict

class Scheduler(object):
    """Used to manage the definitions and reservations of a resource."""

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    def define(self, dates, group=uuid(), raster=15):
        """Defines a list of dates with the given group and raster. Raises
        a DefinitionConflict exception if any date conflicts with an existing
        definition. 

        """

        # TODO add locking here (one resource - one scheduler)

        # Make sure that this span does not overlap another
        for start, end in dates:
            existing = self.any_defined_in_range(start, end)
            if existing:
                raise DefinitionConflict(start, end, existing)

        # Define the timespans
        defines = []
        for start, end in dates:
            span = DefinedTimeSpan(raster=raster)
            span.start = start
            span.end = end
            span.group = group
            span.resource = self.resource

            defines.append(span)

        Session.add_all(defines)

        return group, defines

    def any_defined_in_range(self, start, end):
        """Returns the first defined timespan in the range or None."""
        for defined in self.defined_in_range(start, end):
            return defined

        return None

    def defined_in_range(self, start, end):
        """Yields a list of defined timespans for the current resource."""
        # Query version of DefinedTimeSpan.overlaps
        query = Session.query(DefinedTimeSpan).filter(
            or_(
                and_(
                    DefinedTimeSpan._start <= start,
                    start <= DefinedTimeSpan._end
                ),
                and_(
                    start <= DefinedTimeSpan._start,
                    DefinedTimeSpan._start <= end
                )
            ),
        )

        query = query.filter(DefinedTimeSpan.resource == self.resource)

        for result in query:
            yield result

    def reserve(self, dates):
        """Tries to reserve a list of dates (tuples). If these dates are already
        reserved then the sqlalchemy commit/flash will fail (possibly later).
        """
        reservation = uuid()
        slots_to_reserve = []
        for start, end in dates:
            for span in self.defined_in_range(start, end):
                for slot_start, slot_end in span.possible_dates(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.defined_timespan = span
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
        query = Session.query(DefinedTimeSpan).filter(
            DefinedTimeSpan.group == group
        )

        query.delete()