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
