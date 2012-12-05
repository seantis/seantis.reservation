from datetime import timedelta

from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index

from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.models import customtypes
from seantis.reservation.models.other import OtherModels
from seantis.reservation.models.timestamp import TimestampMixin


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
        types.Enum(u'group', u'allocation', name='reservation_target_type'),
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

    __table_args__ = (
        Index('target_status_ix', 'status', 'target', 'id'),
    )

    def allocations(self):
        Allocation = self.models.Allocation
        query = Session.query(Allocation)
        query = query.filter(Allocation.group == self.target)

        return query

    def timespans(self, start=None, end=None):

        if self.target_type == u'allocation':
            return [(self.start, self.end + timedelta(microseconds=1))]
        elif self.target_type == u'group':
            return [
                (a.display_start, a.display_end) for a in self.allocations()
            ]
        else:
            raise NotImplementedError

    @property
    def title(self):
        return self.email

    @property
    def autoapprovable(self):
        Allocation = self.models.Allocation
        query = self.allocations()
        query = query.filter(Allocation.approve == True)

        return query.count() == 0
