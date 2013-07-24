from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.models.other import OtherModels
from seantis.reservation.models.timestamp import TimestampMixin
from sqlalchemy import types
from sqlalchemy.schema import Column


class BlockedPeriod(TimestampMixin, ORMBase, OtherModels):
    """Defines a period during which reservations for a resource are
    blocked.

    """

    __tablename__ = 'blocked_periods'

    id = Column(types.Integer(), primary_key=True, autoincrement=True)
    resource = Column(customtypes.GUID(), nullable=False)
    token = Column(customtypes.GUID(), nullable=False)
    start = Column(types.DateTime(), nullable=False)
    end = Column(types.DateTime(), nullable=False)
