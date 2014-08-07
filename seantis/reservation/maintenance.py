from logging import getLogger
log = getLogger('seantis.reservation')

import re
import threading

from five import grok

from zope.component import getUtility
from zope.component.hooks import getSite
from zope.interface import Interface

from ZServer.ClockServer import ClockServer

from seantis.reservation import db
from seantis.reservation.base import BaseView
from seantis.reservation.interfaces import IResourceViewedEvent
from seantis.reservation.session import ISessionUtility

_connections = set()  # seantis.reservation database connections
_clockservers = dict()  # list of registered Zope Clockservers

# probably not needed as most operations are atomic and therefore protected
# by the GIL, but it's better to be safe than sorry.
locks = {
    '_clockservers': threading.Lock(),
    '_connections': threading.Lock()
}


# The primary hook to setup maintenance clockservers is the reservation view
# event. It's invoked way too often, but the invocation is fast and it is
# guaranteed to be run on a plone site with seantis.reservation installed,
# setup and in use. Other events like zope startup and traversal events are
# not safe enough to use if one has to rely on a site being setup.
@grok.subscribe(IResourceViewedEvent)
def on_resource_viewed(event):
    period = 15 * 60  # 15 minutes
    register_once_per_connection('/remove-expired-sessions', getSite(), period)


def clear_clockservers():
    """ Clears the clockservers and connections for testing. """

    with locks['_connections']:
        _connections.clear()

    with locks['_clockservers']:
        for cs in _clockservers.values():
            cs.close()
        _clockservers.clear()


def register_once_per_connection(method, site, period):
    """ Registers the given method with a clockserver while making sure
    that the method is only registered once for each seantis.reservation db
    connection defined via the ISessionUtility.

        method => relative to the site root, starts with '/'
                  e.g /remove-expired-sessions

        site   => site with seantis.reservation setup in it

        period => interval by which the method is called by the clockserver

    Returns True if a new server was registered, False if the connection
    was already present.

    """

    assert method.startswith('/')

    connection = getUtility(ISessionUtility).get_dsn(site)

    if connection in _connections:
        return False

    method = '/'.join(site.getPhysicalPath()) + method

    with locks['_connections']:
        _connections.add(connection)

    register_server(method, period)

    return True


def register_server(method, period):
    """ Registers the given method with a clockserver.

    Note that due to it's implementation there's no guarantee that the method
    will be called on time every time. The clockserver checks if a call is due
    every time a request comes in, or every 30 seconds when the asyncore.pollss
    method reaches it's timeout (see Lifetime/__init__.py and
    Python Stdlib/asyncore.py).

    """

    assert method not in _clockservers, "%s is already being used" % method

    with locks['_clockservers']:
        _clockservers[method] = ClockServer(
            method, period, host='localhost', logger=ClockLogger(method)
        )

    return _clockservers[method]


logexpr = re.compile(r'GET [^\s]+ HTTP/[^\s]+ ([0-9]+)')


class ClockLogger(object):
    """ Logs the clock runs by evaluating the log strings. Looks for http
    return codes to do so.

    """

    def __init__(self, method):
        self.method = method

    def return_code(self, msg):
        groups = re.findall(logexpr, msg)
        return groups and int(groups[0]) or None

    def log(self, msg):
        code = self.return_code(msg)

        if not code:
            log.error("ClockServer for %s returned nothing" % self.method)

        if code == 200:
            log.info("ClockServer for %s run successfully" % self.method)
        else:
            log.warn("ClockServer for %s returned %i" % (self.method, code))


class RemoveExpiredSessions(BaseView):
    """ Removes all expired sessions when called. Does not require permission.

    """

    permission = "zope2.View"

    grok.name('remove-expired-sessions')
    grok.require(permission)

    grok.context(Interface)

    def render(self):
        removed = db.remove_expired_reservation_sessions()

        # don't give out the session ids to the public, log instead
        log.info('removed the following reservation sessions: %s' % removed)

        return "removed %i reservation sessions" % len(removed)
