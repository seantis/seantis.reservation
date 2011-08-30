import raster

class TimeSlot(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end

class TimeSpan(object):

    def __init__(self, start, end):
        self.raster = 5
        self.start = start
        self.end = end

    def overlaps(self, start, end):
        start, end = raster.rasterize_span(start, end, self.raster)

        if self.start <= start and start <= self.end:
            return True
        
        if start <= self.start and self.start <= end:
            return True

        return False

    def slots(self, start=None, end=None):
        start = start or self.start
        start = start < self.start and self.start or start
        end = end or self.end
        end = end > self.end and self.end or end

        slots = []
        for start, end in raster.iterate_span(start, end, self.raster):
            slots.append(TimeSlot(start, end))
        
        return slots

    def get_start(self):
        return self._start

    def set_start(self, start):
        self._start = raster.rasterize_start(start, self.raster)
    
    start = property(get_start, set_start)

    def get_end(self):
        return self._end

    def set_end(self, end):
        self._end = raster.rasterize_end(end, self.raster)

    end = property(get_end, set_end)

class DefinedTimeSpan(TimeSpan):

    def __init__(self, start, end, resource, group):
        super(DefinedTimeSpan, self).__init__(start, end)
        self.resource = resource
        self.group