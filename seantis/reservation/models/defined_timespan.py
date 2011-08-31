from sqlalchemy import types
from sqlalchemy.schema import Column

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.raster import rasterize_span
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import rasterize_end
from seantis.reservation.raster import iterate_span

class DefinedTimeSpan(ORMBase):

    __tablename__ = 'defined_timespan'

    id = Column(
        types.Integer(),
        primary_key=True,
        autoincrement=True
    )

    resource = Column(
        customtypes.GUID(),
        nullable=False,
    )

    _start = Column(
        types.DateTime(),
        nullable=False,
    )

    _end = Column(
        types.DateTime(),
        nullable=False
    )

    group = Column(
        types.Unicode(140),
        nullable=True
    )

    _raster = Column(
        types.Integer(),
        nullable=False
    )

    def get_raster(self):
        return self._raster

    def set_raster(self, raster):
        # the raster can only be set once!
        self._raster = not self._raster and raster or self._raster

    raster = property(get_raster, set_raster)

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

    def overlaps(self, start, end):
        start, end = rasterize_span(start, end, self.raster)

        if self.start <= start and start <= self.end:
            return True

        if start <= self.start and self.start <= end:
            return True

        return False

    def open_dates(self, start=None, end=None):
        reserved = [slot.start for slot in self.reserved_slots.all()]
        open_dates = []
        for start, end in self.possible_dates(start, end):
            if not start in reserved:
                open_dates.append((start, end))
        
        return open_dates

    def possible_dates(self, start=None, end=None):
        start = start or self.start
        start = start < self.start and self.start or start

        end = end or self.end
        end = end > self.end and self.end or end

        for start, end in iterate_span(start, end, self.raster):
            yield start, end