from collections import namedtuple
from datetime import timedelta

from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index

from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.models import customtypes
from seantis.reservation.models.other import OtherModels
from seantis.reservation.models.timestamp import TimestampMixin
from seantis.reservation.utils import get_date_range
from seantis.reservation.utils import get_resource_by_uuid


Timespan = namedtuple('Timespan', ['start', 'end', 'allocation_id', 'token'])


class Reservation(TimestampMixin, ORMBase, OtherModels):
    """Describes a pending or approved reservation.

    """

    __tablename__ = 'reservations'

    id = Column(
        types.Integer(),
        primary_key=True,
        autoincrement=True
    )

    token = Column(
        customtypes.GUID(),
        nullable=False,
    )

    target = Column(
        customtypes.GUID(),
        nullable=False,
    )

    target_type = Column(
        types.Enum(u'group', u'allocation', 'recurrence',
                   name='reservation_target_type'),
        nullable=False
    )

    resource = Column(
        customtypes.GUID(),
        nullable=False
    )

    start = Column(
        types.DateTime(),
        nullable=True
    )

    end = Column(
        types.DateTime(),
        nullable=True
    )

    status = Column(
        types.Enum(u'pending', u'approved', name="reservation_status"),
        nullable=False
    )

    data = Column(
        customtypes.JSONEncodedDict(),
        nullable=True
    )

    email = Column(
        types.Unicode(254),
        nullable=False
    )

    session_id = Column(
        customtypes.GUID()
    )

    description = Column(
        types.Unicode(254),
    )

    quota = Column(
        types.Integer(),
        nullable=False
    )

    rrule = Column(types.String)

    __table_args__ = (
        Index('target_status_ix', 'status', 'target', 'id'),
    )

    @classmethod
    def for_allocation(cls, allocation, **args):
        reservation = cls(**args)
        reservation.target_type = u'allocation'
        reservation.status = u'pending'
        reservation.target = allocation.group
        return reservation

    @classmethod
    def for_recurrence(cls, rrule, **args):
        reservation = cls(**args)
        reservation.target_type = u'recurrence'
        reservation.status = u'pending'
        reservation.rrule = rrule
        return reservation

    @classmethod
    def for_group(cls, group, **args):
        reservation = cls(**args)
        reservation.target_type = u'group'
        reservation.status = u'pending'
        reservation.target = group
        return reservation

    @property
    def is_recurrence(self):
        return self.target_type == 'recurrence'

    @property
    def is_group(self):
        return self.target_type == 'group'

    @property
    def is_allocation(self):
        return self.target_type == 'allocation'

    def _target_allocations(self):
        """ Returns the allocations this reservation is targeting. This should
        NOT be confused with db.allocations_by_reservation. The method in
        the db module returns the actual allocations belonging to an approved
        reservation.

        This method only returns the master allocations to get information
        about timespans and other properties. If you don't know exactly
        what you're doing you do not want to use this method as misuse might
        be dangerous.

        """
        Allocation = self.models.Allocation
        query = Session.query(Allocation)
        query = query.filter(Allocation.group == self.target)

        # master allocations only
        query = query.filter(Allocation.resource == Allocation.mirror_of)

        return query

    def timespan_entries(self, start=None, end=None):
        if self.status == 'pending':
            return self._pending_timespans(start, end)
        else:
            return self._approved_timespans(start, end)

    def _pending_timespans(self, start_time, end_time):
        result = []
        for start, end in self.target_dates():
            if start_time and not start >= start_time:
                continue
            if end_time and not end <= end_time:
                continue
            # build tuple containing necessary info for deletion links
            timespan = Timespan(start=start,
                                end=end + timedelta(microseconds=1),
                                allocation_id=None,
                                token=self.token)
            result.append(timespan)
        return result

    def _approved_timespans(self, start, end):
        ReservedSlot = self.models.ReservedSlot
        query = Session.query(ReservedSlot)\
                .filter_by(reservation_token=self.token)
        if start:
            query = query.filter(ReservedSlot.start >= start)
        if end:
            query = query.filter(ReservedSlot.end <= end)

        # find the slots that are still reserved
        result = []
        for start, end in self.target_dates():
            reserved_slot = query.filter(ReservedSlot.start <= end)\
                            .filter(ReservedSlot.end >= start)\
                            .first()
            if not reserved_slot:
                continue
            # build tuple containing necessary info for deletion links
            timespan = Timespan(start=start,
                                end=end + timedelta(microseconds=1),
                                allocation_id=reserved_slot.allocation_id,
                                token=self.token)
            result.append(timespan)
        return result

    def timespans(self):
        """ Return all target_dates that still point to a valid reservation.

        Display an additional microsecond at the end to make the end date
        readable.

        """
        return [(each.start, each.end) for each in self.timespan_entries()]

    def target_dates(self):
        """ Returns the dates this reservation targets. Those should not be
        confused with the dates this reservation actually reserved.

        The reason for this difference is the fact that after the reservation
        is created, certain dates might be removed through removing reserved
        slots.

        This function only returns dates the reservation was originally
        targeted at.

        """
        if self.target_type == u'allocation':
            return ((self.start, self.end),)

        if self.target_type == u'group':
            return self._target_allocations().with_entities(
                self.models.Allocation._start,
                self.models.Allocation._end
            ).all()

        if self.target_type == u'recurrence':
            time_start = self.start.time()
            time_end = self.end.time()

            date_start = self.start.date()
            from dateutil.rrule import rrulestr

            rule = rrulestr(self.rrule, dtstart=date_start)
            return [get_date_range(date, time_start, time_end)
                    for date in rule]

        raise NotImplementedError

    @property
    def title(self):
        return self.email

    @property
    def autoapprovable(self):
        query = self._target_allocations()
        query = query.filter(self.models.Allocation.approve_manually == True)

        # A reservation is deemed autoapprovable if no allocation
        # requires explicit approval

        return query.first() is None

    def get_resource_brain(self):
        return get_resource_by_uuid(self.resource)

    def get_resource(self):
        return self.get_resource_brain().getObject()
