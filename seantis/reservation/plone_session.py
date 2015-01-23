import uuid
from zope.site.hooks import getSite
from Products.CMFCore.utils import getToolByName


session_key = lambda name: '%s:reservation:%s' % (getSite().id, name)


def new_session_id():
    """ Generates a new session id. """

    return uuid.uuid4()


def get_session(context, key):
    """Gets the key from the session."""
    session_manager = getToolByName(context, 'session_data_manager')

    if not session_manager.hasSessionData():
        return None

    session = session_manager.getSessionData()

    if key not in session.keys():
        return None

    return session[key]


def set_session(context, key, value):
    """Stores the given value with the key in the session."""
    session_manager = getToolByName(context, 'session_data_manager')
    session = session_manager.getSessionData()
    session[key] = value


def get_session_id(context):
    """Returns the current session id (models/reservation/session_id), creating
    it first if necessary.

    The session_id is used in the database and it is bound to the browser.
    The same user on different browsers will have different session ids.

    So the seantis.reservation session data is strictly bound to the browser.
    It used to be different, but nobody was using this feature and without
    it we are more secure and we allow for users to share their login (which
    in organizations is not that uncommon)

    """
    skey = session_key('session_id')
    session_id = get_session(context, skey)

    if session_id is None:
        session_id = new_session_id()
        set_session(context, skey, session_id)

    return session_id


def get_email(context):
    return get_session(context, session_key('email')) or None


def set_email(context, email):
    set_session(context, session_key('email'), email)


def get_additional_data(context):
    return get_session(context, session_key('additional_data'))


def set_additional_data(context, data):
    set_session(context, session_key('additional_data'), data)
