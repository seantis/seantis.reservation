import uuid
from zope.site.hooks import getSite


def get_session(context, key):
    """Gets the key from the session."""
    session_manager = context.session_data_manager

    if not session_manager.hasSessionData():
        return None

    session = session_manager.getSessionData()

    if not key in session.keys():
        return None

    return session[key]


def set_session(context, key, value):
    """Stores the given value with the key in the session."""
    session_manager = context.session_data_manager
    session = session_manager.getSessionData()
    session[key] = value


def session_key(name):
    plone = getSite()
    return '%s:reservation:%s' % (plone.id, name)


def get_email(context):
    sid = session_key('email')
    return get_session(context, sid) or None


def get_additional_data(context):
    sid = session_key('additional_data')
    return get_session(context, sid) or None


def get_session_id(context):
    sid = session_key('session_id')
    session_id = get_session(context, sid)
    if session_id is None:
        session_id = uuid.uuid4()
        set_session(context, sid, session_id)
    return session_id


def set_email(context, email):
    sid = session_key('email')
    set_session(context, sid, email)


def set_additional_data(context, data):
    sid = session_key('additional_data')
    set_session(context, sid, data)
