from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.schema import Index
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import backref

from seantis.reservation import ORMBase
from seantis.reservation.raster import rasterize_start, rasterize_end
from seantis.reservation.models import customtypes
from seantis.reservation.models.timestamp import TimestampMixin
from seantis.reservation.models.allocation import Allocation


class ReservedSlot(TimestampMixin, ORMBase):
    """Describes a reserved slot within an allocated timespan."""

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

    allocation_id = Column(
        types.Integer(),
        ForeignKey(Allocation.id),
        nullable=False
    )

    allocation = relationship(
        Allocation,
        primaryjoin=Allocation.id == allocation_id,

        # Reserved_slots are eagerly joined since we usually want both
        # allocation and reserved_slots. There's barely a function which does
        # not need to know about reserved slots when working with allocation.
        backref=backref(
            'reserved_slots',
            lazy='joined',
            cascade='all, delete-orphan'
        )
    )

    reservation_token = Column(
        customtypes.GUID(),
        nullable=False
    )

    __table_args__ = (
        Index('reservation_resource_ix', 'reservation_token', 'resource'),
    )

    def display_start(self):
        return rasterize_start(self.start, self.allocation.raster)

    def display_end(self):
        return rasterize_end(self.end, self.allocation.raster)

    def __eq__(self, other):
        return self.start == other.start and \
            str(self.resource) == str(other.resource)
