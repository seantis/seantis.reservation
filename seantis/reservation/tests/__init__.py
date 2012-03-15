import unittest2 as unittest

from zope.component import getUtility, createObject
from plone.dexterity.interfaces import IDexterityFTI

from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent

from seantis.reservation import setuphandlers
from seantis.reservation.session import getUtility, ISessionUtility

from seantis.reservation.testing import SQL_INTEGRATION_TESTING
from seantis.reservation.testing import SQL_FUNCTIONAL_TESTING

class TestCase(unittest.TestCase):

    def setUp(self):
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

        
        
class IntegrationTestCase(TestCase):
    layer = SQL_INTEGRATION_TESTING

    def setUp(self):
        super(IntegrationTestCase, self).setUp()

class FunctionalTestCase(TestCase):
    layer = SQL_FUNCTIONAL_TESTING