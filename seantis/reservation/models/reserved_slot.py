from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from sqlalchemy.orm import backref

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.models.available import Available

class ReservedSlot(ORMBase):
    """Describes a slot within an Available time which is reserved."""

    __tablename__ = 'reserved_slots'

    resource = Column(
        customtypes.GUID(),
        primary_key=True,
        nullable=False,
        autoincrement=False
    )

    start = Column(
        types.DateTime(),
        primary_key=True,
        nullable=False,
        autoincrement=False
    )

    end = Column(
        types.DateTime(),
        nullable=False
    )

    available_id = Column(
        types.Integer(), 
        ForeignKey(Available.id),
        nullable=False
    )

    available = relation(Available,
        primaryjoin=Available.id==available_id,
        backref=backref('reserved_slots', lazy='dynamic', cascade='all')
    )

    reservation = Column(
        customtypes.GUID(),
        nullable = False
    )