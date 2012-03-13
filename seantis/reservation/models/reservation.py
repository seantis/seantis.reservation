from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index

from seantis.reservation import utils
from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.models import customtypes
from seantis.reservation.models.other import OtherModels

class Reservation(ORMBase, OtherModels):
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
            return [(self.start, self.end)]
        elif self.target_type == u'group':
            return [(a.display_start, a.display_end) for a in self.allocations()]
        else:
            raise NotImplementedError

    def flat_data(self, dictionary):
        result = []

        for key, val in dictionary.items():
            if type(val) == dict:
                result.extend(self.flat_data(val))
            else:
                result.append((key, val))

        return result

    @property
    def title(self):
        data = self.data
        if not data: return self.email

        flat = self.flat_data(data)
        parts = [self.email]
        
        for key, value in flat:
            if key in ('first_name', 'last_name'):
                parts.append(value or u'')
        
        return ' '.join(parts)