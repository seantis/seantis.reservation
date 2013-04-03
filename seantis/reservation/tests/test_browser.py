import json

from datetime import datetime

from seantis.reservation import utils
from seantis.reservation.tests import FunctionalTestCase


class TestBrowser(FunctionalTestCase):

    def setUp(self):
        super(TestBrowser, self).setUp()
        self.baseurl = self.portal.absolute_url()

        browser = self.new_browser()
        browser.login_admin()

        # create a testfolder for each test
        browser.open(self.baseurl + '/createObject?type_name=Folder')

        browser.getControl('Title').value = 'testfolder'
        browser.getControl('Save').click()

        self.assertTrue('no items in this folder' in browser.contents)

        self.admin_browser = browser
        self.folder_url = self.baseurl + '/testfolder'
        self.build_folder_url = lambda url: self.folder_url + url

    def tearDown(self):
        # delete the destfolder again
        self.admin_browser.open(
            self.folder_url + '/delete_confirmation'
        )
        self.admin_browser.getControl('Delete').click()
        self.admin_browser.assert_notfound(self.baseurl + '/testfolder')

        super(TestBrowser, self).tearDown()

    def add_resource(self, name, description=''):
        url = self.build_folder_url

        browser = self.admin_browser
        browser.open(url('/++add++seantis.reservation.resource'))

        browser.getControl('Name').value = name
        browser.getControl('Description').value = description
        browser.getControl('Save').click()

    def add_allocation(self, resource, start, end, partly_available=False):
        url = self.build_folder_url

        browser = self.admin_browser

        s = utils.utctimestamp(start)
        e = utils.utctimestamp(end)

        allocate_url = '/%s/allocate?start=%s&end=%s' % (resource, s, e)
        browser.open(url(allocate_url))

        # Plone formats the English run tests like this: 1:30 AM
        # Python does not do single digit hours so we strip.
        ds = start.strftime('%I:%M %p').lstrip('0')
        de = end.strftime('%I:%M %p').lstrip('0')

        self.assertTrue(ds in browser.contents)
        self.assertTrue(de in browser.contents)

        browser.getControl('Partly available').selected = partly_available
        browser.getControl('Allocate').click()

    def load_slot_data(self, resource, start, end):
        url = self.build_folder_url

        browser = self.admin_browser

        s = utils.utctimestamp(start)
        e = utils.utctimestamp(end)

        slots_url = '/%s/slots?start=%s&end=%s' % (resource, s, e)

        browser.open(url(slots_url))
        return json.loads(browser.contents.replace('\n', ''))

    def test_resource_listing(self):

        url = self.build_folder_url

        browser = self.new_browser()
        browser.login_admin()

        browser.open(url('/selectViewTemplate?templateId=resource_listing'))

        self.add_resource('Resource 1', 'Description 1')

        browser.open(self.folder_url)
        self.assertEqual(browser.contents.count('Click to reserve'), 1)
        self.assertTrue('Resource 1' in browser.contents)
        self.assertTrue('Description 1' in browser.contents)

        self.add_resource('Resource 2')

        browser.open(self.folder_url)
        self.assertEqual(browser.contents.count('Click to reserve'), 2)
        self.assertTrue('Resource 2' in browser.contents)

    def test_singlecalendar(self):

        url = self.build_folder_url

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('Test')

        browser.open(url('/test'))

        self.assertTrue('singlecalendar' in browser.contents)
        self.assertFalse('multicalendar' in browser.contents)

        self.assertTrue('test' in browser.contents)

        # the title of the parent is not used as a prefix in this case
        self.assertFalse('testfolder - test' in browser.contents)

    def test_multicalendar(self):

        url = self.build_folder_url

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('one')
        self.add_resource('two')

        browser.open(url('/one/@@uuid'))
        uuid = browser.contents

        browser.open(url('/two?compare_to=%s' % uuid))

        self.assertFalse('singlecalendar' in browser.contents)
        self.assertTrue('multicalendar' in browser.contents)

        # the title of the parent is used as a prefix
        self.assertTrue('testfolder - one' in browser.contents)
        self.assertTrue('testfolder - two' in browser.contents)

    def test_resource_properties(self):

        url = self.build_folder_url

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('test-resource')

        browser.open(url('/test-resource/@@edit'))
        browser.getControl('First hour of the day').value = "10"
        browser.getControl('Last hour of the day').value = "12"

        browser.getControl(name='form.widgets.available_views:list').value = [
            'month', 'agendaWeek'
        ]

        browser.getControl(name='form.widgets.selected_view:list').value = [
            'month'
        ]

        browser.getControl('Save').click()

        self.assertTrue('"minTime": 10' in browser.contents)
        self.assertTrue('"maxTime": 12' in browser.contents)
        self.assertTrue('"right": "month, agendaWeek"' in browser.contents)
        self.assertTrue('"defaultView": "month"' in browser.contents)

    def test_invalid_allocation_missing_email_regression(self):

        # if an email is entered but the reservation is invalid the email
        # may not disappear

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 3, 4, 15, 0)
        end = datetime(2013, 3, 4, 16, 0)

        self.add_resource('regression')
        self.add_allocation('regression', start, end, partly_available=True)

        slots = self.load_slot_data('regression', start, end)
        self.assertEqual(len(slots), 1)

        # the reserve_url is the default url
        browser.open(slots[0]['url'])

        # enter some invalid dates and an email. The form should then show an
        # error, but not forget about the email like it used to
        browser.getControl('End').value = '1:00 PM'
        browser.getControl('Email').value = 'test@example.com'

        browser.getControl('Reserve').click()

        self.assertTrue('Reservation out of bounds' in browser.contents)
        self.assertTrue('test@example.com' in browser.contents)

        # really reserve this time
        browser.getControl('End').value = '4:00 PM'
        browser.getControl('Reserve').click()

        self.assertTrue('Your reservations' in browser.contents)
