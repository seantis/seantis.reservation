from datetime import timedelta
from itertools import groupby

from sqlalchemy import types
from sqlalchemy.schema import Column

from seantis.reservation import ORMBase
from seantis.reservation import utils
from seantis.reservation.models import customtypes
from seantis.reservation.raster import rasterize_span
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import rasterize_end
from seantis.reservation.raster import iterate_span
from seantis.reservation import Session


class Allocation(ORMBase):
    """Describes a timespan within which one or many timeslots can be reserved.

    """

    __tablename__ = 'allocations'

    id = Column(types.Integer(), primary_key=True, autoincrement=True)
    resource = Column(customtypes.GUID(), nullable=False)
    mirror_of = Column(customtypes.GUID())
    group = Column(types.Unicode(100), nullable=False)
    quota = Column(types.Integer(), default=1)
    partly_available = Column(types.Boolean(), default=False)

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

    @property
    def display_start(self):
        """Does nothing but to form a nice pair to display_end."""
        return self.start

    @property
    def display_end(self):
        """Returns the end plus one microsecond (nicer display)."""
        return self.end + timedelta(microseconds=1)

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

    def contains(self, start, end):
        """ Returns true if the current timespan contains the given start
        and end date.

        """
        start, end = rasterize_span(start, end, self.raster)
        return self.start <= start and end <= self.end

    def free_slots(self, start=None, end=None):
        """ Returns the slots which are not yet reserved."""
        reserved = [slot.start for slot in self.reserved_slots.all()]
        slots = []
        for start, end in self.all_slots(start, end):
            if not start in reserved:
                slots.append((start, end))
        
        return slots

    def align_dates(self, start=None, end=None):
        """ Aligns the given dates to the start and end date of the allocation."""

        start = start or self.start
        start = start < self.start and self.start or start

        end = end or self.end
        end = end > self.end and self.end or end

        return start, end

    def all_slots(self, start=None, end=None):
        """ Returns the slots which exist with this timespan. Reserved or free.

        """
        start, end = self.align_dates(start, end)

        if self.partly_available:
            for start, end in iterate_span(start, end, self.raster):
                yield start, end
        else:
            yield start, end + timedelta(microseconds=-1)

    def is_available(self, start, end):
        """ Returns true if the given daterange is completely available. """
        assert(self.overlaps(start, end))
        
        reserved = [slot.start for slot in self.reserved_slots.all()]
        for start, end in self.all_slots(start, end):
            if start in reserved:
                return False

        return True

    @property
    def availability(self):
        """Returns the availability in percent."""

        total = sum(1 for s in self.all_slots())
        count = self.reserved_slots.count()

        if total == count:
            return 0.0

        if count == 0:
            return 100.0

        # Can't think of a reason why this should happen..
        assert(total > 0)

        # ..but if it does I prefer an assertion to a division through zero
        return 100.0 - (float(count) / float(total) * 100.0)

    @property
    def in_group(self):
        """Returns true if the event is in any group."""

        # If the group is a uuid, it's probably a single event
        if utils.is_uuid(self.group):
            return False

        query = Session.query(Allocation)
        query = query.filter(Allocation.resource == self.resource)
        query = query.filter(Allocation.group == self.group)

        return query.count() > 1

    def availability_partitions(self):
        """Partitions the space between start and end into blocks of either
        free or reserved time. Each block has a percentage representing the
        space the block occupies compared to the size of the whole allocation.

        The blocks are ordered from start to end. Each block is an item with two
        values. The first being the percentage, the second being true if the
        block is reserved.

        So given an allocation that goes from 8 to 9 and a reservation that goes
        from 8:15 until 8:30 we get the following blocks:

        [
            (25%, False),
            (25%, True),
            (50%, False)
        ]

        This is useful to divide an allocation block into different divs on the
        frontend, indicating to the user which parts of an allocation are reserved.

        """
        reserved = [r.start for r in self.reserved_slots.all()]
        if (len(reserved) == 0):
            return [(100.0, False)]

        # Get the percentage one slot represents
        slots = list(self.all_slots())
        step = 100.0 / float(len(slots))

        # Create an entry for each slot with either True or False
        pieces = [s[0] in reserved for s in slots]
            
        # Group by the true/false values in the pieces and sum up the percentage
        partitions = []
        for flag, group in groupby(pieces, key=lambda p: p):
            percentage = len(list(group)) * step
            partitions.append([percentage, flag])
        
        # Make sure to get rid of floating point rounding errors
        total = sum([p[0] for p in partitions])
        diff = 100.0 - total

        partitions[-1:][0][0] -= diff

        return partitions