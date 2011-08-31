from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from sqlalchemy.orm import backref

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes
from seantis.reservation.models.defined_timespan import DefinedTimeSpan

class ReservedTimeSlot(ORMBase):

    __tablename__ = 'reserved_timeslot'

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

    timespan_id = Column(
        types.Integer(), 
        ForeignKey('defined_timespan.id'),
        nullable=False
    )

    defined_timespan = relation(DefinedTimeSpan,
        primaryjoin=DefinedTimeSpan.id==timespan_id,
        backref=backref('reserved_slots', lazy='dynamic', cascade='all')
    )