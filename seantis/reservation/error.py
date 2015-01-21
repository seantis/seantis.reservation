from sqlalchemy.exc import IntegrityError
from psycopg2.extensions import TransactionRollbackError
from sqlalchemy.orm.exc import NoResultFound

from libres.modules.errors import (
    ModifiedReadOnlySession,
    DirtyReadOnlySession,
    InvalidAllocationError,
    ReservationTooLong,
    ReservationParametersInvalid,
    AlreadyReservedError,
    QuotaOverLimit,
    QuotaImpossible,
    InvalidQuota,
    InvalidReservationError,
    NotReservableError,
    NoReservationsToConfirm,
    InvalidReservationToken,
    OverlappingAllocationError,
    AffectedReservationError,
    AffectedPendingReservationError,
    TimerangeTooLong
)

from seantis.reservation import _


# pyflakes
ModifiedReadOnlySession
DirtyReadOnlySession


class ReservationError(Exception):
    pass


class CustomReservationError(ReservationError):

    def __init__(self, msg):
        self.msg = msg


class ThrottleBlock(ReservationError):
    pass


errormap = {

    OverlappingAllocationError:
    _(u'A conflicting allocation exists for the requested time period.'),

    AffectedReservationError:
    _(u'An existing reservation would be affected by the requested change.'),

    AffectedPendingReservationError:
    _(u'A pending reservation would be affected by the requested change.'),

    TransactionRollbackError:
    _(u'The resource is being edited by someone else. Please try again.'),

    NoResultFound:
    _(u'The item does no longer exist.'),

    AlreadyReservedError:
    _(u'The requested period is no longer available.'),

    IntegrityError:
    _(u'Invalid change. Your request may have already been processed '
      u'earlier.'),

    NotReservableError:
    _(u'No reservable slot found.'),

    ReservationTooLong:
    _(u"Reservations can't be made for more than 24 hours at a time"),

    ThrottleBlock:
    _(u'Too many reservations in a short time. Wait for a moment before '
      u'trying again.'),

    ReservationParametersInvalid:
    _(u'The given reservation paramters are invalid.'),

    InvalidReservationToken:
    _(u'The given reservation token is invalid.'),

    InvalidReservationError:
    _(u'The given reservation paramters are invalid.'),

    QuotaOverLimit:
    _(u'The requested number of reservations is higher than allowed.'),

    InvalidQuota:
    _(u'The requested quota is invalid (must be at least one).'),

    QuotaImpossible:
    _(u'The allocation does not have enough spots to possibly satisfy the '
      u'requested number of reservations.'),

    InvalidAllocationError:
    _(u'The resulting allocation would be invalid.'),

    NoReservationsToConfirm:
    _(u'No reservations to confirm.'),

    TimerangeTooLong:
    _(u'The given timerange is longer than the existing allocation.')
}
