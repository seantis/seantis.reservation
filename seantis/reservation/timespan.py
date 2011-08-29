from zope.interface import Implements

from interfaces import ITimespan
from interfaces import IAvailableSpan
from interfaces import IReservedSpan


class Timespan(object):
    Implements(ITimespan)

    def __init__(self, start, end, group, resource):
        self.start = start
        self.end = end
        self.group = group
        self.resource = resource


class AvailableSpan(Timespan):
    Implements(IAvailableSpan)


class ReservedSpan(Timespan):
    Implements(IReservedSpan)

