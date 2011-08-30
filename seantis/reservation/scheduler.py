from seantis.reservation.timespans import TimeSpan

class Scheduler(object):

    def __init__(self, reservable):
        self.resid = reservable.uid()
        self.defined = []
        self.reserved = {}

    def define(self, start, end):
        if self.defined_in_range(start, end):
            return False

        self.defined.append(TimeSpan(start, end))
        return True

    def defined_in_range(self, start, end):
        defined = []

        for span in self.defined:
            if span.overlaps(start, end):
                defined.append(span)

        return defined

    def reserve(self, timespans):
        defined = []
        for span in timespans:
            defined.extend(self.defined_in_range(span.start, span.end))

        to_reserve = []
        for request in timespans:
            for d in self.defined_in_range(span.start, span.end):
                for slot in d.slots(request.start, request.end):
                    to_reserve.append(slot)
        
        for slot in to_reserve:
            key = '%s%s' % (self.resid, slot.start)
            if key in self.reserved:
                raise KeyError
            
            self.reserved[key] = slot

def test():
    from seantis.reservation.timespans import TimeSpan
    from datetime import datetime
    
    class Resource(object):
        def uid(self):
            return 1

    sc = Scheduler(Resource())
    start = datetime(2011, 1, 1, 15, 0)
    end = datetime(2011, 1, 1, 15, 59)
    sc.define(start, end)

    span = TimeSpan(start, end)
    sc.reserve((span, ))
    return sc