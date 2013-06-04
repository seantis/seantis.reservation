from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import pkg_resources

from seantis.reservation import _

try:
    pkg_resources.get_distribution('psycopg2')
    from psycopg2.extensions import TransactionRollbackError
    HAS_PSYCOPG2 = True
except pkg_resources.DistributionNotFound:
    HAS_PSYCOPG2 = False


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


class AffectedPendingReservationError(AffectedReservationError):
    pass


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


class InvalidReservationToken(ReservationError):
    pass


class InvalidReservationError(ReservationError):
    pass


class QuotaOverLimit(ReservationError):
    pass


class InvalidQuota(ReservationError):
    pass


class QuotaImpossible(ReservationError):
    pass


class InvalidAllocationError(ReservationError):
    pass


errormap = {

    OverlappingAllocationError:
    _(u'A conflicting allocation exists for the requested time period.'),

    AffectedReservationError:
    _(u'An existing reservation would be affected by the requested change'),

    AffectedPendingReservationError:
    _(u'A pending reservation would be affected by the requested change'),

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
    _(u'The requested reservation quota is higher than allowed.'),

    InvalidQuota:
    _(u'The requested quota is invalid (must be at least one).'),

    QuotaImpossible:
    _(u'The allocation does not have enough spots to possibly satisfy the '
      u'requested reservation quota.'),

    InvalidAllocationError:
    _(u'The resulting allocation would be invalid'),
}

if HAS_PSYCOPG2:
    errormap[TransactionRollbackError] =  _(u'The resource is being edited by '
                                            'someone else. Please try again.')
