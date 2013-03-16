import os
import unittest2 as unittest

from tempfile import NamedTemporaryFile

from zope import event
from zope.component import getUtility
from zope.security.management import newInteraction, endInteraction

from Acquisition import aq_base
from zope.component import getSiteManager
from Products.CMFPlone.tests.utils import MockMailHost
from Products.MailHost.interfaces import IMailHost

from plone.testing import z2
from plone.dexterity.utils import createContentInContainer
from plone.app.testing import TEST_USER_NAME, TEST_USER_ID
from plone.app.testing import login, logout, setRoles

from seantis.reservation import setuphandlers
from seantis.reservation.utils import getSite
from seantis.reservation.session import ISessionUtility

from seantis.reservation.testing import SQL_INTEGRATION_TESTING
from seantis.reservation.testing import SQL_FUNCTIONAL_TESTING

from seantis.reservation import maintenance

from Products.CMFCore.utils import getToolByName


class TestCase(unittest.TestCase):

    def setUp(self):

        self.app = self.layer['app']
        self.portal = self.layer['portal']

        # setup mock mail host
        self._original_MailHost = self.portal.MailHost
        self.portal.MailHost = mailhost = MockMailHost('MailHost')
        sm = getSiteManager(context=self.portal)
        sm.unregisterUtility(provided=IMailHost)
        sm.registerUtility(mailhost, provided=IMailHost)

        self.portal.email_from_address = 'noreply@example.com'

        # remove all test event subscribers
        event.subscribers = [
            e for e in event.subscribers if type(e) != TestEventSubscriber
        ]
        setuphandlers.dbsetup(None)

        self.logged_in = False

    def tearDown(self):

        # reset original mail host
        self.portal.MailHost = self._original_MailHost
        sm = getSiteManager(context=self.portal)
        sm.unregisterUtility(provided=IMailHost)
        sm.registerUtility(
            aq_base(self._original_MailHost), provided=IMailHost
        )

        util = getUtility(ISessionUtility)
        util.sessionstore.readonly.rollback()
        util.sessionstore.serial.rollback()

        maintenance.clear_clockservers()

        self.logout()

    def request(self):
        return self.layer['request']

    def login_manager(self):
        login(self.portal, TEST_USER_NAME)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

    def login_admin(self):
        z2.login(self.app['acl_users'], 'admin')

    def new_browser(self):
        browser = BetterBrowser(self.app)
        browser.portal = self.portal
        browser.handleErrors = False

        self.portal.error_log._ignored_exceptions = ()

        def raising(self, info):
            import traceback
            traceback.print_tb(info[2])
            print info[1]

        from Products.SiteErrorLog.SiteErrorLog import SiteErrorLog
        SiteErrorLog.raising = raising

        return browser

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

    def create_resource(self):
        return createContentInContainer(
            getSite(), 'seantis.reservation.resource'
        )

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
        return self.event is not None

    def reset(self):
        self.event = None


# we need something like seantis.plone-tools because this exists
# in seantis.dir.events as well at the moment
class BetterBrowser(z2.Browser):

    portal = None

    def login(self, user, password):
        self.open(self.portal.absolute_url() + "/login_form")
        self.getControl(name='__ac_name').value = user
        self.getControl(name='__ac_password').value = password
        self.getControl(name='submit').click()

        assert 'logout' in self.contents

    def logout(self):
        self.open(self.portal.absolute_url() + "/logout")

        assert 'logged out' in self.contents

    def login_admin(self):
        self.login('admin', 'secret')

    def login_testuser(self):
        self.login('test-user', 'secret')

    def assert_http_exception(self, url, exception):
        self.portal.error_log._ignored_exceptions = ()
        self.portal.acl_users.credentials_cookie_auth.login_path = ""

        expected = False
        try:
            self.open(url)
        except Exception, e:

            # zope does not always raise unathorized exceptions with the
            # correct class signature, so we need to do this thing:
            expected = e.__repr__().startswith(exception)

            if not expected:
                raise

        assert expected

    def assert_unauthorized(self, url):
        self.assert_http_exception(url, 'Unauthorized')

    def assert_notfound(self, url):
        self.assert_http_exception(url, 'NotFound')

    def show(self):
        """ Opens the current contents in the default system browser """
        tempfile = NamedTemporaryFile(delete=False)
        tempfile.write(self.contents)
        tempfile.close()

        os.rename(tempfile.name, tempfile.name + '.html')
        os.system("open " + tempfile.name + '.html')

    def set_date(self, widget, date):
        self.getControl(name='%s-year' % widget).value = str(date.year)
        self.getControl(name='%s-month' % widget).value = [str(date.month)]
        self.getControl(name='%s-day' % widget).value = str(date.day)
        self.getControl(name='%s-hour' % widget).value = str(date.hour)
        self.getControl(name='%s-minute' % widget).value = str(date.minute)


# to use with integration where security interactions need to be done manually
class IntegrationTestCase(TestCase):
    layer = SQL_INTEGRATION_TESTING

    def setUp(self):
        super(IntegrationTestCase, self).setUp()
        # setup security
        newInteraction()

    def tearDown(self):
        endInteraction()
        super(IntegrationTestCase, self).tearDown()


# to use with the browser which does it's own security interactions
class FunctionalTestCase(TestCase):
    layer = SQL_FUNCTIONAL_TESTING
