from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.models.other import OtherModels

class Reservation(ORMBase, OtherModels):
    """Describes a pending or confirmed reservation and may as such act as
    a list of confirmed reservations or a waiting list.

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
        types.Enum(u'pending', u'confirmed', name="reservation_status"), 
        nullable=False
    )

    data = Column(
        customtypes.JSONEncodedDict(),
        nullable=True
    )

    __table_args__ = (
        Index('target_status_ix', 'status', 'target', 'id'),
    )