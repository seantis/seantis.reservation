from z3c.saconfig import Session
from sqlalchemy import _and

from seantis.reservation.models import DefinedTimeSpan
from seantis.reservation.models import ReservedTimeSlot

class Scheduler(object):

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    def define(self, start, end, group=None, raster=15):
        # TODO add locking here

        # Make sure that this span does not overlap another
        if self.any_defined_in_range(start, end):
            return None

        span = DefinedTimeSpan()
        span.start = start
        span.end = end
        span.resource = self.resource
        span.group = self.group

        Session.add(span)

        return span

    def any_defined_in_range(self, start, end):
        for defined in self.defined_in_range(start, end):
            return True

        return False

    def defined_in_range(self, start, end):
        query = Session.query(DefinedTimeSpan).filter(
            _and(
                DefinedTimeSpan.start>=start,
                DefinedTimeSpan.end<=end
            )
        )

        for span in query:
            if span.overlaps(start, end):
                yield span

    def reserve(self, dates):
        slots_to_reserve = []
        for start, end in dates:
            for span in self.defined_in_range(start, end):
                for slot_start, slot_end in span.possible_dates(start, end):
                    slot = ReservedTimeSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.defined_timespan = span
                    slot.resource = slot.resource

                    slots_to_reserve.append(slot)
        
        Session.add_all(slots_to_reserve)