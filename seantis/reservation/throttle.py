from datetime import datetime

from zope.security import checkPermission

from seantis.reservation import settings
from seantis.reservation import error
from seantis.reservation import utils


def seconds_required(context):
    if checkPermission('seantis.reservation.UnthrottledReservations', context):
        return 0
    return settings.get('throttle_minutes') * 60


def session_get(context, key):
    man = context.session_data_manager
    return man.hasSessionData() and man.getSessionData().get(key) or None


def session_set(context, key, value):
    man = context.session_data_manager
    man.getSessionData()[key] = value


def apply(context, name):
    key = 'throttle_' + name
    last_change = session_get(context, key)

    if last_change:
        delta = (datetime.today() - last_change)
        seconds_since = utils.total_timedelta_seconds(delta)

        if seconds_since < seconds_required(context):
            raise error.ThrottleBlock

    session_set(context, key, datetime.today())

    # return a function which resets the throttle if called
    return lambda: last_change and session_set(context, key, last_change)


def throttled(function, context, name):
    def wrap():
        abort = apply(context, name)
        try:
            function()
        except:
            abort()
            raise
    return wrap
