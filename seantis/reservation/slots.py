from zope.interface import implements

from interfaces import ITimeSlot
from interfaces import IAvailableSlot
from interfaces import IReservedSlot


class TimeSlot(object):
    implements(ITimeSlot)

    def __init__(self, start, end, resource, group=None):
        self.start = start
        self.end = end
        self.resource = resource
        self.group = group

    def overlaps(self, start, end):
        if self.start <= start and start <= self.end:
            return True
        
        if start <= self.start and self.start <= end:
            return True

        return False


class AvailableSlot(TimeSlot):
    implements(IAvailableSlot)


class ReservedSlot(TimeSlot):
    implements(IReservedSlot)


class SlotManager(object):

    def __init__(self, reservable):
        self.uid = reservable.uid()
        self.available = []
        self.reserved = []
    
    def define(self, timeslots):
        """Add timeslots to the database."""
        self.available.extend(timeslots)

    def available_slots(self, start, end):
        return (s for s in self.available if s.overlaps(start, end))

    def reserved_slots(self, start, end):
        return (r for r in self.reserved if r.overlaps(start, end))

    def is_available(self, start, end):
        for reserved in self.reserved_slots(start, end):
            if reserved.overlaps(start, end):
                return False
        
        return True

    def reserve(self, start, end):
        assert(self.is_available(start, end))

        self.reserved.append(ReservedSlot(start, end))