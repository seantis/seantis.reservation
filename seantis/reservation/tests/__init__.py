import unittest2 as unittest

from zope import event
from zope.component import getUtility, createObject
from plone.dexterity.interfaces import IDexterityFTI

from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent

from seantis.reservation import setuphandlers
from seantis.reservation.session import ISessionUtility

from seantis.reservation.testing import SQL_INTEGRATION_TESTING
from seantis.reservation.testing import SQL_FUNCTIONAL_TESTING

class TestCase(unittest.TestCase):

    def setUp(self):
        # remove all test event subscribers
        event.subscribers = [e for e in event.subscribers if type(e) != TestEventSubscriber]
        setuphandlers.dbsetup(None)

    def tearDown(self):
        util = getUtility(ISessionUtility)
        util.threadstore.readonly.rollback()
        util.threadstore.serial.rollback()

    def request(self):
        return self.layer['request']

    def create_resource(self):
        fti = getUtility(IDexterityFTI, name='seantis.reservation.resource')
        resource = createObject(fti.factory)
        notify(ObjectCreatedEvent(resource))

        return resource

    def subscribe(self, eventclass):
        subscriber = TestEventSubscriber(eventclass)
        event.subscribers.append(subscriber)
        return subscriber

class TestEventSubscriber(object):

    def __init__(self, eventclass):
        self.eventclass = eventclass
        self.event = None

    def __call__(self, event):
        if type(event) is self.eventclass:
            self.event = event

    def was_fired(self):
        return self.event != None

    def reset(self):
        self.event = None
        
class IntegrationTestCase(TestCase):
    layer = SQL_INTEGRATION_TESTING

    def setUp(self):
        super(IntegrationTestCase, self).setUp()

class FunctionalTestCase(TestCase):
    layer = SQL_FUNCTIONAL_TESTING