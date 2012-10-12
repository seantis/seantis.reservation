import unittest2 as unittest

from zope import event
from zope.component import getUtility
from zope.security.management import newInteraction, endInteraction

from Acquisition import aq_base
from zope.component import getSiteManager
from Products.CMFPlone.tests.utils import MockMailHost
from Products.MailHost.interfaces import IMailHost

from plone.dexterity.utils import createContentInContainer
from plone.app.testing import TEST_USER_NAME, TEST_USER_ID
from plone.app.testing import login, logout, setRoles

from seantis.reservation import setuphandlers
from seantis.reservation.utils import getSite
from seantis.reservation.session import ISessionUtility

from seantis.reservation.testing import SQL_INTEGRATION_TESTING
from seantis.reservation.testing import SQL_FUNCTIONAL_TESTING

from AccessControl import getSecurityManager
from Products.CMFCore.utils import getToolByName

class TestCase(unittest.TestCase):

    def setUp(self):
        # setup mock mail host
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal._original_MailHost = self.portal.MailHost
        self.portal.MailHost = mailhost = MockMailHost('MailHost')
        sm = getSiteManager(context=self.portal)
        sm.unregisterUtility(provided=IMailHost)
        sm.registerUtility(mailhost, provided=IMailHost)

        self.portal.email_from_address = 'noreply@example.com'

        # remove all test event subscribers
        event.subscribers = [e for e in event.subscribers if type(e) != TestEventSubscriber]
        setuphandlers.dbsetup(None)

        self.logged_in = False

        # setup security
        newInteraction()

    def tearDown(self):
        self.portal.MailHost = self.portal._original_MailHost
        sm = getSiteManager(context=self.portal)
        sm.unregisterUtility(provided=IMailHost)
        sm.registerUtility(aq_base(self.portal._original_MailHost), provided=IMailHost)

        util = getUtility(ISessionUtility)
        util.sessionstore.readonly.rollback()
        util.sessionstore.serial.rollback()

        self.logout()
        endInteraction()

    def request(self):
        return self.layer['request']

    def login_as_manager(self):
        login(self.portal, TEST_USER_NAME)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.logged_in = True

    def assign_reservation_manager(self, email, resource):
        username = email.split('@')[0]
        password = 'hunter2'

        acl_users = getToolByName(self.portal, 'acl_users')
        acl_users.userFolderAddUser(username, password, ['Member'], [])
        
        resource.manage_setLocalRoles(username, ['Reservation-Manager'])

        user = acl_users.getUser(username)
        properties = acl_users.mutable_properties.getPropertiesForUser(user)
        properties._properties['email'] = email
        acl_users.mutable_properties.setPropertiesForUser(user, properties)

        # the email will be there after the next retrieval of the user
        user = acl_users.getUser(username)
        assert user.getProperty('email') == email
        
        return username, password

    def logout(self):
        logout()
        self.logged_in = False

    def create_resource(self):
        return createContentInContainer(getSite(), 'seantis.reservation.resource')

    def subscribe(self, eventclass):
        subscriber = TestEventSubscriber(eventclass)
        event.subscribers.append(subscriber)
        return subscriber

    @property
    def mailhost(self):
        return self.portal.MailHost

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