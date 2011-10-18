from sqlalchemy import types
from sqlalchemy.schema import Column

from seantis.reservation import ORMBase
from seantis.reservation.models import customtypes

class ResourceProperty(ORMBase):
    """Caches properties of resources."""

    __tablename__ = 'resource_properties'

    resource = Column(
        customtypes.GUID(),
        primary_key=True,
        nullable=False,
        autoincrement=False
    )

    quota = Column(
        types.Integer(),
        nullable=False
    )