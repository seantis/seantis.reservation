from datetime import datetime

from zope.component.hooks import getSite
from zope.security import checkPermission

from seantis.reservation import settings
from seantis.reservation import error
from seantis.reservation import utils


def is_throttling_active():
    return not checkPermission(
        'seantis.reservation.UnthrottledReservations', getSite()
    )


def seconds_required():
    if not is_throttling_active():
        return 0
    return settings.get('throttle_minutes') * 60


def session_get(key):
    man = getSite().session_data_manager
    return man.hasSessionData() and man.getSessionData().get(key) or None


def session_set(key, value):
    man = getSite().session_data_manager
    man.getSessionData()[key] = value


def apply(name):
    key = 'throttle_' + name
    last_change = session_get(key)

    if last_change:
        delta = (datetime.today() - last_change)
        seconds_since = utils.total_timedelta_seconds(delta)

        if seconds_since < seconds_required():
            raise error.ThrottleBlock

    session_set(key, datetime.today())

    # return a function which resets the throttle if called
    return lambda: last_change and session_set(key, last_change)


def throttled(function, name):
    def wrap():
        abort = apply(name)
        try:
            return function()
        except:
            abort()
            raise
    return wrap
