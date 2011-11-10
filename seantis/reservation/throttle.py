from datetime import datetime

from seantis.reservation import error
from seantis.reservation import utils

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
        
        if seconds_since < 60:
            raise error.ThrottleBlock

    session_set(context, key, datetime.today())