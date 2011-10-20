from seantis.reservation import ORMBase
from seantis.reservation import Session

def dbsetup(context):
    ORMBase.metadata.create_all(Session.bind)