from datetime import timedelta
from itertools import groupby

from sqlalchemy import types
from sqlalchemy.sql import and_, or_
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import object_session 
from sqlalchemy.orm.util import has_identity 

from seantis.reservation import ORMBase
from seantis.reservation import utils
from seantis.reservation.models import customtypes
from seantis.reservation.raster import rasterize_span
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import rasterize_end
from seantis.reservation.raster import iterate_span
from seantis.reservation import Session
from seantis.reservation.models.other import OtherModels

class Allocation(ORMBase, OtherModels):
    """Describes a timespan within which one or many timeslots can be reserved.

    """

    __tablename__ = 'allocations'

    id = Column(types.Integer(), primary_key=True, autoincrement=True)
    resource = Column(customtypes.GUID(), nullable=False)
    mirror_of = Column(customtypes.GUID())
    group = Column(customtypes.GUID(), nullable=False)
    quota = Column(types.Integer(), default=1)
    partly_available = Column(types.Boolean(), default=False)
    approve = Column(types.Boolean(), default=True)

    waitinglist_spots = Column(types.Integer(), default=0)
    # waiting list spots are interpreted like this:
    # <1 = no spots on the waiting list
    # >0 = n spots on the waiting list

    _start = Column(types.DateTime(), nullable=False)
    _end = Column(types.DateTime(), nullable=False)
    _raster = Column(types.Integer(), nullable=False)

    __table_args__ = (
            Index('mirror_resource_ix', 'mirror_of', 'resource'), 
            UniqueConstraint('resource', '_start', name='resource_start_ix')
        )

    def copy(self):
        allocation = Allocation()
        allocation.resource = self.resource
        allocation.mirror_of = self.mirror_of
        allocation.group = self.group
        allocation.quota = self.quota
        allocation.partly_available = self.partly_available
        allocation.approve = self.approve
        allocation.waitinglist_spots = self.waitinglist_spots
        allocation._start = self._start
        allocation._end = self._end
        allocation._raster = self._raster
        return allocation

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
        return utils.overlaps(start, end, self.start, self.end)

    def contains(self, start, end):
        """ Returns true if the current timespan contains the given start
        and end date.

        """
        start, end = rasterize_span(start, end, self.raster)
        return self.start <= start and end <= self.end

    def free_slots(self, start=None, end=None):
        """ Returns the slots which are not yet reserved."""
        reserved = [slot.start for slot in self.reserved_slots]
        
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
            yield self.start, self.end

    def is_available(self, start=None, end=None):
        """ Returns true if the given daterange is completely available. """

        if not (start and end):
            start, end = self.start, self.end

        assert(self.overlaps(start, end))
        
        reserved = [slot.start for slot in self.reserved_slots]
        for start, end in self.all_slots(start, end):
            if start in reserved:
                return False

        return True

    @property
    def has_waitinglist(self):
        return self.waitinglist_spots != 0

    def pending_reservations(self):
        """ Returns the number of pending reservations. 

        This is not necessarily the same as the number of used spots in the 
        waitinglist as allocations without a waitinglist may still have pending 
        reservations up to the set quota. 

        The reason is that non-waitinglist allocations still use the two-phase
        reservation with the first phase being pending reservations.

        For those, there are no spots in the waiting list, but pending reservations
        up to the number of open quota spots may still be added.

        For allocations with a waiting list the pending reservations equal the
        number of used spots in the waiting list. This ensures that a waitinglist
        of 100 never has more than 100 entries, no matter if we count the spots toward
        the list or toward the unused quota.

        """
        Reservation = self.models.Reservation
        query = Session.query(Reservation.id)
        query = query.filter(Reservation.target == self.group)
        query = query.filter(Reservation.status == u'pending')

        return query.count()

    def open_waitinglist_spots(self):

        used = self.pending_reservations()
        available = self.waitinglist_spots

        return max(available - used, 0)

    @property
    def availability(self):
        """Returns the availability in percent."""

        if self.partly_available:
            total = sum(1 for s in self.all_slots())
        else:
            total = 1

        count = len(self.reserved_slots)

        if total == count:
            return 0.0

        if count == 0:
            return 100.0

        return 100.0 - (float(count) / float(total) * 100.0)

    @property
    def in_group(self):
        """Returns true if the event is in any group."""
        
        query = Session.query(Allocation.id)
        query = query.filter(Allocation.resource == self.resource)
        query = query.filter(Allocation.group == self.group)
        query = query.limit(2)

        return len(query.all()) > 1

    @property
    def is_separate(self):
        if self.partly_available:
            return True

        if self.in_group:
            return False

        return True

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
        if (len(self.reserved_slots) == 0):
            return [(100.0, False)]

        reserved = [r.start for r in self.reserved_slots]

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

    @property
    def is_transient(self):
        """True if the allocation does not exist in the database, and is not 
        about to be written to the database. If an allocation is transient it
        means that the given instance only exists in memory.

        See:
        http://www.sqlalchemy.org/docs/orm/session.html#quickie-intro-to-object-states
        http://stackoverflow.com/questions/3885601/sqlalchemy-get-object-instance-state

        """
        
        return object_session(self) is None and not has_identity(self)

    @property
    def is_master(self):
        """True if the allocation is a master allocation."""

        return self.resource == self.mirror_of

    def siblings(self, imaginary=True):
        """Returns the master/mirrors group this allocation is part of. 

        If 'imaginary' is true, inexistant mirrors are created on the fly.
        those mirrors are transient (see self.is_transient)

        """

        # this function should always have itself in the result
        if not imaginary and self.is_transient:
            assert False, 'the resulting list would not contain this allocation'

        if self.quota == 1:
            assert(self.is_master)
            return [self]

        query = Session.query(Allocation)
        query = query.filter(Allocation.mirror_of == self.mirror_of)
        query = query.filter(Allocation._start == self._start)

        existing = dict(((e.resource, e) for e in query))

        master = self.is_master and self or existing[self.mirror_of]
        existing[master.resource] = master

        uuids = utils.generate_uuids(master.resource, master.quota)
        imaginary = imaginary and (master.quota - len(existing)) or 0

        siblings = [master]
        for uuid in uuids:
            if uuid in existing:
                siblings.append(existing[uuid])
            elif imaginary > 0:
                allocation = master.copy()
                allocation.resource = uuid
                siblings.append(allocation)

                imaginary -= 1
        
        return siblings