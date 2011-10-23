from sqlalchemy.exc import IntegrityError
from psycopg2.extensions import TransactionRollbackError
from sqlalchemy.orm.exc import NoResultFound

class ReservationError(Exception):
    pass

class OverlappingAllocationError(ReservationError):

    def __init__(self, start, end, existing):
        self.start = start
        self.end = end
        self.existing = existing

class AffectedReservationError(ReservationError):

    def __init__(self, existing):
        self.existing = existing

class AlreadyReservedError(ReservationError):
    pass

class DirtyReadOnlySession(ReservationError):
    pass

class ModifiedReadOnlySession(ReservationError):
    pass