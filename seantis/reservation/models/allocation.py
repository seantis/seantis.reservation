from datetime import timedelta, time
from itertools import groupby

from sqlalchemy import types
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
from seantis.reservation.models.timestamp import TimestampMixin


class Allocation(TimestampMixin, ORMBase, OtherModels):
    """Describes a timespan within which one or many timeslots can be
    reserved.

    There's an important concept to understand before working with allocations.
    The resource uuid of an alloction is not always pointing to the actual
    resource.

    A resource may in fact be a real resource, or an imaginary resource with
    a uuid derived from the real resource. This is a somewhat historical
    artifact.

    If you need to know which allocations belong to a real resource, the
    mirror_of field is what's relevant. The originally created allocation
    with the real_resource is also called the master-allocation and it is
    the one allocation with mirror_of and resource being equal.

    When in doubt look at the managed_* functions of seantis.reservation.db's
    Scheduler class.

    """

    __tablename__ = 'allocations'

    id = Column(types.Integer(), primary_key=True, autoincrement=True)
    resource = Column(customtypes.GUID(), nullable=False)
    mirror_of = Column(customtypes.GUID(), nullable=False)
    group = Column(customtypes.GUID(), nullable=False)
    quota = Column(types.Integer(), default=1)
    partly_available = Column(types.Boolean(), default=False)
    approve_manually = Column(types.Boolean(), default=False)

    reservation_quota_limit = Column(
        types.Integer(), default=0, nullable=False
    )

    # The dates are stored without any timzone information (unaware).
    # Therefore the times are implicitly stored in the timezone the resource
    # resides in.

    # This is fine and dandy as long as all resources are in the same timezone.
    # If they are not problems arise. So in the future the resource should
    # carry a timezone property which is applied to the dates which will then
    # be stored in UTC

    # => TODO
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
        allocation.approve_manually = self.approve_manually
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

    @property
    def whole_day(self):
        """True if the allocation is a whole-day allocation.

        A whole-day allocation is not really special. It's just an allocation
        which starts at 0:00 and ends at 24:00 (or 23:59:59'999).

        As such it can actually also span multiple days, only hours and minutes
        count.

        The use of this is to display allocations spanning days differently.
        """

        s, e = self.display_start, self.display_end
        assert s != e  # this can never be, except when caused by cosmic rays

        return utils.whole_day(s, e)

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
        """ Aligns the given dates to the start and end date of the
        allocation.

        """

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

        assert self.overlaps(start, end)

        reserved = [slot.start for slot in self.reserved_slots]
        for start, end in self.all_slots(start, end):
            if start in reserved:
                return False

        return True

    def limit_timespan(self, start, end):
        """ Takes the given timespan and moves the start/end date to
        the closest reservable slot. So if 10:00 - 11:00 is requested it will

        - on a partly available allocation return 10:00 - 11:00 if the raster
          allows for that

        - on a non-partly available allocation return the start/end date of
          the allocation itself.

        The resulting times are combined with the allocations start/end date
        to form a datetime. (time in, datetime out -> maybe not the best idea)

        """
        if self.partly_available:
            assert isinstance(start, time)
            assert isinstance(end, time)

            s, e = utils.get_date_range(self.start.date(), start, end)

            if self.display_end < e:
                e = self.display_end

            if self.display_start > s:
                s = self.display_start

            s, e = rasterize_span(s, e, self.raster)

            return s, e + timedelta(microseconds=1)
        else:
            return self.display_start, self.display_end

    @property
    def pending_reservations(self):
        """ Returns the pending reservations query for this allocation.
        As the pending reservations target the group and not a specific
        allocation this function returns the same value for masters and
        mirrors.

        """
        Reservation = self.models.Reservation
        query = Session.query(Reservation.id)
        query = query.filter(Reservation.target == self.group)
        query = query.filter(Reservation.status == u'pending')

        return query

    @property
    def waitinglist_length(self):
        return self.pending_reservations.count()

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
        """True if the event is in any group."""

        query = Session.query(Allocation.id)
        query = query.filter(Allocation.resource == self.resource)
        query = query.filter(Allocation.group == self.group)
        query = query.limit(2)

        return len(query.all()) > 1

    @property
    def is_separate(self):
        """True if available separately (as opposed to available only as
        part of a group)."""
        if self.partly_available:
            return True

        if self.in_group:
            return False

        return True

    def availability_partitions(self):
        """Partitions the space between start and end into blocks of either
        free or reserved time. Each block has a percentage representing the
        space the block occupies compared to the size of the whole allocation.

        The blocks are ordered from start to end. Each block is an item with
        two values. The first being the percentage, the second being true if
        the block is reserved.

        So given an allocation that goes from 8 to 9 and a reservation that
        goes from 8:15 until 8:30 we get the following blocks:

        [
            (25%, False),
            (25%, True),
            (50%, False)
        ]

        This is useful to divide an allocation block into different divs on the
        frontend, indicating to the user which parts of an allocation are
        reserved.

        """
        if (len(self.reserved_slots) == 0):
            return [(100.0, False)]

        reserved = [r.start for r in self.reserved_slots]

        # Get the percentage one slot represents
        slots = list(self.all_slots())
        step = 100.0 / float(len(slots))

        # Create an entry for each slot with either True or False
        pieces = [s[0] in reserved for s in slots]

        # Group by the true/false values in the pieces and sum up the
        # percentage
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
        http://www.sqlalchemy.org/docs/orm/session.html
        #quickie-intro-to-object-states
        http://stackoverflow.com/questions/3885601/
        sqlalchemy-get-object-instance-state

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
            assert False, \
                'the resulting list would not contain this allocation'

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
