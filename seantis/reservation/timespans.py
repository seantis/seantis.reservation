from zope.interface import implements

from interfaces import ITimeSpan
from interfaces import IAvailableSpan
from interfaces import IReservedSpan

class TimeSpan(object):
    implements(ITimeSpan)

    def __init__(self, start, end, resource=None, group=None):
        self.start = start
        self.end = end
        self.resource = resource
        self.group = group

    def __repr__(self):
        classname = self.__class__.__name__
        return '%s(%s, %s, %s, %s)' \
                % (classname, self.start, self.end, self.resource, self.group)

    def overlaps(self, start, end):
        if self.start <= start and start <= self.end:
            return True
        
        if start <= self.start and self.start <= end:
            return True

        return False


class AvailableSpan(TimeSpan):
    implements(IAvailableSpan)


class ReservedSpan(TimeSpan):
    implements(IReservedSpan)