from sqlalchemy import types
from sqlalchemy.schema import Column

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.raster import rasterize_span
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import rasterize_end
from seantis.reservation.raster import iterate_span

class Available(ORMBase):

    __tablename__ = 'availables'

    id = Column(types.Integer(), primary_key=True, autoincrement=True)
    resource = Column(customtypes.GUID(), nullable=False)
    group = Column(customtypes.GUID(), nullable=False)

    _start = Column(types.DateTime(), nullable=False)
    _end = Column(types.DateTime(), nullable=False)
    _raster = Column(types.Integer(), nullable=False)

    def get_start(self):
        return self._start
    
    def set_start(self, start):
        self._start = rasterize_start(start, self.raster)

    start = property(get_start, set_start)

    def get_end(self):
        return self._end

    def set_end(self, end):
        self._end = rasterize_end(end, self.raster)

    end = property(get_end, set_end)

    def get_raster(self):
        return self._raster

    def set_raster(self, raster):
        # the raster can only be set once!
        assert(not self._raster)
        self._raster = raster

    raster = property(get_raster, set_raster)

    def overlaps(self, start, end):
        """ Returns true if the current timespan overlaps with the given
        start and end date.

        """
        start, end = rasterize_span(start, end, self.raster)

        if self.start <= start and start <= self.end:
            return True

        if start <= self.start and self.start <= end:
            return True

        return False

    def slots(self, start=None, end=None):
        """ Returns the slots which are not yet reserved."""
        reserved = [slot.start for slot in self.reserved_slots.all()]
        slots = []
        for start, end in self.all_slots(start, end):
            if not start in reserved:
                slots.append((start, end))
        
        return slots

    def all_slots(self, start=None, end=None):
        """ Returns the slots which exist with this timespan. Does not
        account for slots which are already reserved.

        """
        start = start or self.start
        start = start < self.start and self.start or start

        end = end or self.end
        end = end > self.end and self.end or end

        for start, end in iterate_span(start, end, self.raster):
            yield start, end