from sqlalchemy.exc import IntegrityError
from psycopg2.extensions import TransactionRollbackError
from sqlalchemy.orm.exc import NoResultFound

from seantis.reservation import _

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

class NotReservableError(ReservationError):
    pass

class ReservationTooLong(ReservationError):
    pass

class ThrottleBlock(ReservationError):
    pass

class ReservationParametersInvalid(ReservationError):
    pass

class FullWaitingList(ReservationError):
    pass

class InvalidReservationToken(ReservationError):
    pass

errormap = {

    OverlappingAllocationError: 
    _(u'A conflicting allocation exists for the requested time period.'),

    AffectedReservationError:
    _(u'An existing reservation would be affected by the requested change'),

    TransactionRollbackError:
    _(u'The resource is being edited by someone else. Please try again.'),

    NoResultFound:
    _(u'The item does no longer exist.'),

    AlreadyReservedError:
    _(u'The requested period is no longer available and there is no waiting list.'),

    IntegrityError:
    _(u'Invalid change. Your request may have already been processed earlier.'),

    NotReservableError:
    _(u'No reservable slot found.'),

    ReservationTooLong:
    _(u"Reservations can't be made for more than 24 hours at a time"),

    ThrottleBlock:
    _(u'Too many reservations in a short time. Wait for a moment before trying again.'),

    ReservationParametersInvalid:
    _(u'The given reservation paramters are invalid.'),

    FullWaitingList:
    _(u'The requested period is no longer available and the waiting list is full.'),

    InvalidReservationToken:
    _(u'The given reservation token is invalid.'),
}