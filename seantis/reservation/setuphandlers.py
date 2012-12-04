from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.session import serialized


@serialized
def dbsetup(context):
    ORMBase.metadata.create_all(Session.bind)
