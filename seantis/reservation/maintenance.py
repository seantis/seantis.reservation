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
from seantis.reservation.interfaces import IResourceViewedEvent
from seantis.reservation.session import ISessionUtility


connections = set()
clockservers = dict()
lock = threading.Lock()


@grok.subscribe(IResourceViewedEvent)
def on_resource_viewed(event):
    register_site(getSite())


def register_site(site):

    session_util = getUtility(ISessionUtility)
    connection = session_util.get_dsn(site)

    if connection in connections:
        return

    method = '/'.join(site.getPhysicalPath()) + '/remove-expired-sessions'

    lock.acquire()
    try:
        connections.add(connection)
        _register_server(method, 10)
    finally:
        lock.release()


def _register_server(method, period):

    assert method not in clockservers, "%s is already being used" % method

    clockservers[method] = ClockServer(
        method, period, host='localhost', logger=ClockLogger(method)
    )

    return clockservers[method]


logexpr = re.compile(r'GET [^\s]+ HTTP/[^\s]+ ([0-9]+)')


class ClockLogger(object):

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


class RemoveExpiredSessions(grok.View):

    permission = "zope2.View"

    grok.name('remove-expired-sessions')
    grok.require(permission)

    grok.context(Interface)

    def render(self):
        removed = db.remove_expired_reservation_sessions()

        # don't give out the session ids to the public, log instead
        log.info('removed the following reservation sessions: %s' % removed)

        return "removed %i reservation sessions" % len(removed)
