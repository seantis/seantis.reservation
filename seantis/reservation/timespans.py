import raster

class TimeSpan(object):

    def __init__(self, start, end):
        self.raster = 5
        self.start = start
        self.end = end

    def overlaps(self, start, end):
        if self.start <= start and start <= self.end:
            return True
        
        if start <= self.start and self.start <= end:
            return True

        return False

    def xslots(self):
        for slot in raster.span_iterate(self.start, self.end, self.raster):
            yield slot

    def slots(self):
        return list(self.xslots())

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