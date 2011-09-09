from seantis.reservation import ORMBase
from z3c.saconfig import Session

def dbsetup(context):
    session = Session()
    ORMBase.metadata.create_all(session.bind)