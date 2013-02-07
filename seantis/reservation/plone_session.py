import uuid
from zope.site.hooks import getSite
from Products.CMFCore.utils import getToolByName


session_key = lambda name: '%s:reservation:%s' % (getSite().id, name)

# users need to get a predictable uuid valid for each plone site
# ideally, a plone site would provide us with a uuid as a namespace
# from which to generate further uuids, but it doesn't, so we need
# to do that ourselves. The root namespace is used to get a plone site
# specific uuid which is then used as a namespace for the users.
root_namespace = uuid.UUID('7ad36f77-a10c-4b62-857c-a9a4ff7222a0')


def generate_session_id(context):
    """ Generates a new session id. """

    membership = getToolByName(context, 'portal_membership')

    # anonymous users get random uuids
    if membership.isAnonymousUser():
        return uuid.uuid4()

    # logged in users get ids which are predictable for each plone site
    namespace = uuid.uuid5(root_namespace, str(getSite().id))
    return uuid.uuid5(namespace, str(membership.getId()))


def get_session(context, key):
    """Gets the key from the session."""
    session_manager = getToolByName(context, 'session_data_manager')

    if not session_manager.hasSessionData():
        return None

    session = session_manager.getSessionData()

    if not key in session.keys():
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

    """
    skey = session_key('session_id')
    session_id = get_session(context, skey)

    if session_id is None:
        session_id = generate_session_id(context)
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
