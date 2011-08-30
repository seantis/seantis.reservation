from seantis.reservation.timespans import AvailableSpan
from seantis.reservation.timespans import ReservedSpan

from seantis.reservation.error import AlreadyDefinedError
from seantis.reservation.error import NotAvailableError

class Scheduler(object):

    def __init__(self, reservable):
        self.resid = reservable.uid()
        self.available = []
        self.reserved = []

    def define(self, start, end, group=None, rrule=None):
        assert(start < end)

        if rrule:
            duration = end - start
            dates = [(s, s + duration) for s in rrule]
        else:
            dates = ((start, end))
        
        timespans = []
        for start, end in dates:
            timespan = AvailableSpan(start, end, self.resid, group)

            if self.is_defined(start, end):
                raise AlreadyDefinedError(timespan)
            
            timespans.append(timespan)


        self.available.extend(timespans)

    def available_spans(self, start, end):
        return (s for s in self.available if s.overlaps(start, end))

    def reserved_spans(self, start, end):
        return (r for r in self.reserved if r.overlaps(start, end))

    def is_defined(self, start, end):
        for available in self.avalable_spans(start, end):
            return True

        return False

    def is_available(self, start, end):
        for reserved in self.reserved_spans(start, end):
            if reserved.overlaps(start, end):
                return False
        
        return True

    def reserve(self, timespan):
        if not self.is_available(timespan.start, timespan.end):
            raise NotAvailableError(timespan)

        reservedspan = ReservedSpan(timespan.start, timespan.end)
        reservedspan.group = timespan.group
        reservedspan.resource = self.resid

        self.reserved.append(reservedspan)