import json
import transaction
from itertools import chain

from zope.component import queryUtility
from Products.CMFCore.interfaces import IPropertiesTool

from datetime import datetime

from seantis.reservation import utils
from seantis.reservation import db
from seantis.reservation.tests import FunctionalTestCase


class FormsetField(object):
    def __init__(self, name, type, default=None):
        self.name = name
        self.type = type
        self.default = default


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
        self.infolder = lambda url: self.folder_url + url
        self.formsets = []

    def tearDown(self):
        browser = self.admin_browser

        # delete the destfolder again
        browser.open(self.infolder('/delete_confirmation'))
        browser.getControl('Delete').click()

        browser.assert_notfound(self.baseurl + '/testfolder')

        # delete the formsests
        if self.formsets:
            browser.open('/dexterity-types')

            for formset in self.formsets:
                input_name = 'crud-edit.{}.widgets.select:list'.format(formset)
                browser.getControl(name=input_name).value = [True]

            browser.getControl('Delete').click()

            for formset in self.formsets:
                browser.assert_notfound('/dexterity-types/{}'.format(formset))

        super(TestBrowser, self).tearDown()

    def add_resource(self, name, description='', formsets=[], action=None):
        browser = self.admin_browser

        browser.open(self.infolder('/++add++seantis.reservation.resource'))
        browser.getControl('Name').value = name
        browser.getControl('Description').value = description

        for formset in formsets:
            browser.getControl(formset).selected = True

        browser.getControl('Save').click()

        if action:
            browser.open(self.infolder(
                '/{}/content_status_modify?workflow_action={}'.format(
                    name, action
                )
            ))

    def add_allocation(
        self, resource, start, end,
        partly_available=False,
        quota=1,
        quota_limit=1,
        recurrence=None,
        separately=None,
    ):

        browser = self.admin_browser

        s = utils.utctimestamp(start)
        e = utils.utctimestamp(end)

        allocate_url = '/%s/allocate?start=%s&end=%s' % (resource, s, e)
        browser.open(self.infolder(allocate_url))

        # Plone formats the English run tests like this: 1:30 AM
        # Python does not do single digit hours so we strip.
        ds = start.strftime('%I:%M %p').lstrip('0')
        de = end.strftime('%I:%M %p').lstrip('0')

        self.assertTrue(ds in browser.contents)
        self.assertTrue(de in browser.contents)

        browser.getControl('Partly available').selected = partly_available
        browser.getControl('Quota', index=0).value = str(quota)
        browser.getControl('Reservation Quota Limit').value = str(quota_limit)
        if recurrence:
            browser.getControl('Recurrence').value = recurrence
        if separately is not None:
            browser.getControl('Separately reservable').selected = separately
        browser.getControl('Allocate').click()

    def add_formset(self, name, fields, for_managers=False):
        browser = self.admin_browser

        browser.open('/dexterity-types/@@add-type')
        browser.getControl('Type Name').value = name
        browser.getControl('Short Name').value = name

        browser.getControl('Add').click()

        self.formsets.append(name)

        for field in fields:

            browser.open('/dexterity-types/{}/@@add-field'.format(name))
            browser.getControl('Title').value = field.name
            browser.getControl('Short Name').value = field.name
            browser.getControl('Field type').value = (field.type, )
            browser.getControl('Add').click()

            # no requirements for now, there are issues with defaults
            browser.open('/dexterity-types/{}/{}'.format(name, field.name))
            browser.getControl('Required').selected = False
            browser.getControl('Save').click()

        browser.open('/dexterity-types/{}/fields'.format(name))

        for field in (f for f in fields if f.default is not None):

            ctl = browser.getControl(name='form.widgets.{}'.format(field.name))
            ctl.value = field.default

        browser.getControl('Save Defaults').click()

        browser.open('/dexterity-types/{}/@@behaviors'.format(name))

        standard = 'Reservation Formset'
        managers = 'Reservation Manager Formset'

        browser.getControl(standard).selected = not for_managers
        browser.getControl(managers).selected = for_managers

        browser.getControl('Save').click()

    def load_slot_data(self, resource, start, end):

        browser = self.admin_browser

        s = utils.utctimestamp(start)
        e = utils.utctimestamp(end)

        slots_url = '/%s/slots?start=%s&end=%s' % (resource, s, e)

        browser.open(self.infolder(slots_url))
        return json.loads(browser.contents.replace('\n', ''))

    def allocation_menu(self, resource, start, end):

        slots = self.load_slot_data(resource, start, end)
        assert len(slots) == 1

        menu = {}
        for group, entries in slots[0]['menu'].items():
            for e in entries:
                menu[e['name'].lower()] = e['url'].replace('/plone', '')

        return menu

    def test_regression_recurrence_invariant_not_working(self):
        """Make sure that partly available allocations can only be reserved
        separately when recurrence is set.

        """
        url = self.build_folder_url

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('recurrence')

        browser.open(url('/recurrence'))

        start = datetime(2013, 3, 4, 15, 0)
        end = datetime(2013, 3, 4, 16, 0)

        self.add_allocation('recurrence', start, end,
                            partly_available=True,
                            recurrence="RRULE:FREQ=DAILY;COUNT=2",
                            separately=False)

        self.assertIn('Partly available allocations can only be reserved',
                      str(self.admin_browser.query("div.field.error .error")))

    def test_resource_listing(self):

        browser = self.new_browser()
        browser.login_admin()

        browser.open(
            self.infolder('/selectViewTemplate?templateId=resource_listing')
        )

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

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('Test')

        browser.open(self.infolder('/test'))

        self.assertTrue('singlecalendar' in browser.contents)
        self.assertFalse('multicalendar' in browser.contents)

        self.assertTrue('test' in browser.contents)

        # the title of the parent is not used as a prefix in this case
        self.assertFalse('testfolder - test' in browser.contents)

    def test_multicalendar(self):

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('one')
        self.add_resource('two')

        browser.open(self.infolder('/one/@@uuid'))
        uuid = browser.contents

        browser.open(self.infolder('/two?compare_to=%s' % uuid))

        self.assertFalse('singlecalendar' in browser.contents)
        self.assertTrue('multicalendar' in browser.contents)

        # the title of the parent is used as a prefix
        self.assertTrue('testfolder - one' in browser.contents)
        self.assertTrue('testfolder - two' in browser.contents)

    def test_resource_properties(self):

        browser = self.new_browser()
        browser.login_admin()

        self.add_resource('test-resource')

        browser.open(self.infolder('/test-resource/@@edit'))
        browser.getControl('First hour of the day').value = "10"
        browser.getControl('Last hour of the day').value = "12"

        browser.getControl(name='form.widgets.available_views:list').value = [
            'month', 'agendaWeek'
        ]

        try:     # plone 4.3
            control = 'form.widgets.selected_view'
            browser.getControl(name=control).value = ['month']
        except:  # plone 4.2
            control = 'form.widgets.selected_view:list'
            browser.getControl(name=control).value = ['month']

        browser.getControl('Save').click()

        self.assertTrue('"minTime": 10' in browser.contents)
        self.assertTrue('"maxTime": 12' in browser.contents)
        self.assertTrue('"right": "month, agendaWeek"' in browser.contents)
        self.assertTrue('"defaultView": "month"' in browser.contents)

    def test_render_disabled_dates_partly(self):

        # ensure that the disabled date/time is rendered again after
        # submitting a form

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 9, 20, 15, 0)
        end = datetime(2013, 9, 20, 16, 0)

        self.add_resource('render')

        allocation = ('render', start, end)
        self.add_allocation(*allocation, partly_available=True)

        browser.open(self.allocation_menu(*allocation)['reserve'])

        unchanging_values = [
            ('#form-widgets-day-day', '20'),
            ('#form-widgets-day-month option[selected="selected"]', '9'),
            ('#form-widgets-day-year', '2013'),
        ]

        changing_values = [
            ('#form-widgets-start_time', '3:00 PM'),
            ('#form-widgets-end_time', '4:00 PM')
        ]

        for selector, value in chain(unchanging_values, changing_values):
            self.assertEqual(browser.query(selector).val(), value)

        browser.getControl('Start').value = '3:15 PM'
        browser.getControl('End').value = '3:45 PM'

        # not entering anything should lead to the form again with the still
        # filled out controls
        browser.getControl('Reserve').click()

        changing_values = [
            ('#form-widgets-start_time', '3:15 PM'),
            ('#form-widgets-end_time', '3:45 PM')
        ]

        for selector, value in chain(unchanging_values, changing_values):
            self.assertEqual(browser.query(selector).val(), value)

    def test_render_disabled_dates_non_partly(self):

        # ensure that the disabled date/time is rendered again after
        # submitting a form (on not partly_available allocations)

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 9, 20, 15, 0)
        end = datetime(2013, 9, 20, 16, 0)

        self.add_resource('render')

        allocation = ('render', start, end)
        self.add_allocation(*allocation, partly_available=False)

        browser.open(self.allocation_menu(*allocation)['reserve'])

        unchanging_values = [
            ('#form-widgets-day-day', '20'),
            ('#form-widgets-day-month option[selected="selected"]', '9'),
            ('#form-widgets-day-year', '2013'),
            ('#form-widgets-start_time', '3:00 PM'),
            ('#form-widgets-end_time', '4:00 PM')
        ]

        for selector, value in unchanging_values:
            self.assertEqual(browser.query(selector).val(), value)

        # not entering anything should lead to the form again with the still
        # filled out controls
        browser.getControl('Reserve').click()

        for selector, value in unchanging_values:
            self.assertEqual(browser.query(selector).val(), value)

    def test_invalid_allocation_missing_email_regression(self):

        # if an email is entered but the reservation is invalid the email
        # may not disappear

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 3, 4, 15, 0)
        end = datetime(2013, 3, 4, 16, 0)

        self.add_resource('regression')

        allocation = ('regression', start, end)
        self.add_allocation(*allocation, partly_available=True)

        browser.open(self.allocation_menu(*allocation)['reserve'])

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

    def test_over_quota_limit_regression(self):

        # if a quota is reserved which is over the allowed amount the quota
        # must not just be changed, but there should be an error

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 3, 4, 15, 0)
        end = datetime(2013, 3, 4, 16, 0)

        self.add_resource('regression')

        allocation = ('regression', start, end)
        self.add_allocation(*allocation, quota=4, quota_limit=2)
        browser.open(self.allocation_menu(*allocation)['reserve'])

        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Quota', index=0).value = '3'

        browser.getControl('Reserve').click()

        self.assertTrue('quota is higher than allowed' in browser.contents)
        self.assertEqual('3', browser.getControl('Quota', index=0).value)

    def test_overreserve_regression(self):

        # it was possible to add reservations to the waitinglist before,
        # even if there was no waitinglist allowed.
        # it needed a quota to be higher than the free spots

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 6, 2, 14, 0)
        end = datetime(2013, 6, 2, 16, 0)

        self.add_resource('overreserve')
        allocation = ('overreserve', start, end)
        self.add_allocation(*allocation, quota=5, quota_limit=5)

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Quota', index=0).value = '3'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Quota', index=0).value = '3'

        browser.getControl('Reserve').click()
        self.assertTrue(
            'The requested period is no longer available' in browser.contents
        )

        browser.open(self.infolder('/overreserve/your-reservations'))
        self.assertFalse('limitedList' in browser.contents)
        self.assertFalse('your-reservation-quota' in browser.contents)

    def test_throttling(self):

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 6, 2, 14, 0)
        end = datetime(2013, 6, 2, 16, 0)

        self.add_resource('throttled')
        allocation = ('throttled', start, end)
        self.add_allocation(*allocation, quota=5, quota_limit=5)

        browser.open(self.infolder(
            '/throttled/content_status_modify?workflow_action=publish'
        ))

        browser.logout()

        # validation issues don't lead to throttling (missing email here)
        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Quota', index=0).value = '1'
        browser.getControl('Reserve').click()
        browser.getControl('Reserve').click()
        self.assertFalse('Too many reservations' in browser.contents)

        # real reservations however do
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()
        self.assertFalse('Too many reservations' in browser.contents)

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Quota', index=0).value = '1'
        browser.getControl('Reserve').click()
        self.assertTrue('Too many reservations' in browser.contents)

    def test_your_reservations_context_regression(self):

        # calling the 'your-reservations' view did not work outside of
        # the resource context, even though that view should work independently
        # of context

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 9, 13, 11, 0)
        end = datetime(2013, 9, 13, 12, 0)

        self.add_resource('yours')
        allocation = ('yours', start, end)
        self.add_allocation(*allocation, quota=2)

        # it works on the resource context
        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        # but it should also work somewhere else
        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()

        browser.open(self.infolder('/your-reservations'))
        browser.getControl('Submit Reservations').click()

    def test_your_reservations_removal(self):
        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 9, 13, 11, 0)
        end = datetime(2013, 9, 13, 12, 0)

        self.add_resource('removal')
        allocation = ('removal', start, end)
        self.add_allocation(*allocation, quota=2)

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()

        browser.open(self.infolder('/removal'))
        self.assertTrue('13.09.2013 11:00 - 12:00' in browser.contents)

        browser.getLink('Remove').click()
        browser.open(self.infolder('/removal'))

        self.assertFalse('13.09.2013 11:00 - 12:00' in browser.contents)

    def test_reservation_approval(self):

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 6, 21, 13, 0)
        end = datetime(2013, 6, 21, 17, 0)

        self.add_resource('approval')

        allocation = ('approval', start, end)
        self.add_allocation(*allocation, approve_manually=True)
        menu = self.allocation_menu(*allocation)
        browser.open(menu['reserve'])

        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()

        browser.getControl('Submit Reservations').click()

        browser.open(menu['manage'])

        self.assertTrue('Approve' in browser.contents)
        self.assertTrue('Deny' in browser.contents)

        browser.getLink('Approve').click()

        self.assertTrue('Concerned Dates' in browser.contents)
        self.assertTrue('21.06.2013 13:00 - 17:00' in browser.contents)

        browser.getControl('Approve').click()
        browser.open(menu['manage'])

        self.assertTrue('Revoke' in browser.contents)
        self.assertFalse('Approve' in browser.contents)

    def test_reservation_formsets(self):

        browser = self.admin_browser

        self.add_formset(
            'public', [FormsetField('name', 'Text')], for_managers=False
        )

        self.add_formset(
            'private', [
                FormsetField('price', 'Integer', '31415927'),
                FormsetField('comment', 'Text')
            ], for_managers=True
        )

        self.add_resource(
            'formsets', formsets=['public', 'private'], action='publish'
        )

        start = datetime(2013, 6, 27, 13, 37)
        end = datetime(2013, 6, 27, 17, 15)

        allocation = ['formsets', start, end]
        self.add_allocation(*allocation)
        menu = self.allocation_menu(*allocation)

        # admins see all form elements when reserving
        browser.open(menu['reserve'])

        self.assertTrue('public' in browser.contents)
        self.assertTrue('private' in browser.contents)

        # normal users don't
        anonymous = self.new_browser()
        anonymous.open(menu['reserve'])

        self.assertTrue('public' in anonymous.contents)
        self.assertFalse('private' in anonymous.contents)

        # if the normal user does the reservation, the formset defaults are
        # written even for manager formsets
        anonymous.getControl('Email').value = 'test@example.com'
        anonymous.getControl('Reserve').click()
        anonymous.getControl('Submit Reservations').click()

        # this can be verified on the manage-page
        browser.open(menu['manage'])
        self.assertTrue('31415927' in browser.contents)
        self.assertFalse('comment' in browser.contents)

        # the manager can at this point change the values
        browser.getLink('Edit Formdata').click()

        browser.getControl('comment').value = 'no comment'
        browser.getControl('Save').click()

        browser.open(menu['manage'])
        self.assertTrue('no comment' in browser.contents)

    @db.serialized
    def test_resource_removal(self):

        browser = self.admin_browser

        # have one resource with data during the run, to check that there's
        # no bleed over through the other tests

        self.add_resource('keeper')
        browser.open(self.infolder('/keeper/@@uuid'))
        uuid = unicode(browser.contents)

        keeper = db.Scheduler(uuid)

        self.assertEqual(keeper.managed_allocations().count(), 0)
        self.assertEqual(keeper.managed_reservations().count(), 0)
        self.assertEqual(keeper.managed_reserved_slots().count(), 0)

        dates = [
            datetime(2013, 7, 2, 10, 15), datetime(2013, 7, 2, 10, 30)
        ]
        keeper.allocate(dates, raster=15)

        token = keeper.reserve(u'test@example.com', dates)
        keeper.approve_reservation(token)

        transaction.commit()  # delete_confirmation will rollback
                              # dropping all SQL statements

        self.assertEqual(keeper.managed_allocations().count(), 1)
        self.assertEqual(keeper.managed_reservations().count(), 1)
        self.assertEqual(keeper.managed_reserved_slots().count(), 1)

        def run_test():
            self.add_resource('removal')
            browser.open(self.infolder('/removal/@@uuid'))
            uuid = unicode(browser.contents)

            scheduler = db.Scheduler(uuid)

            self.assertEqual(scheduler.managed_allocations().count(), 0)
            self.assertEqual(scheduler.managed_reservations().count(), 0)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 0)

            scheduler.allocate(dates, raster=15)

            token = scheduler.reserve(u'test@example.com', dates)
            scheduler.approve_reservation(token)

            transaction.commit()  # delete_confirmation will rollback
                                  # dropping all SQL statements

            self.assertEqual(scheduler.managed_allocations().count(), 1)
            self.assertEqual(scheduler.managed_reservations().count(), 1)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 1)

            # linkintegrity will cause IObjectRemovedEvent to be fired,
            # but the transaction will be rolled back
            browser.open(self.infolder('/removal/delete_confirmation'))
            self.assertEqual(scheduler.managed_allocations().count(), 1)
            self.assertEqual(scheduler.managed_reservations().count(), 1)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 1)

            browser.getControl('Cancel').click()
            self.assertEqual(scheduler.managed_allocations().count(), 1)
            self.assertEqual(scheduler.managed_reservations().count(), 1)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 1)

            browser.open(self.infolder('/removal/delete_confirmation'))
            browser.getControl('Delete').click()
            self.assertEqual(scheduler.managed_allocations().count(), 0)
            self.assertEqual(scheduler.managed_reservations().count(), 0)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 0)

        # run once with link integrity enabled, once disabled
        ptool = queryUtility(IPropertiesTool)
        props = getattr(ptool, 'site_properties', None)

        props.enable_link_integrity_checks = True
        transaction.commit()
        run_test()

        self.assertEqual(keeper.managed_allocations().count(), 1)
        self.assertEqual(keeper.managed_reservations().count(), 1)
        self.assertEqual(keeper.managed_reserved_slots().count(), 1)

        props.enable_link_integrity_checks = False
        transaction.commit()
        run_test()

        self.assertEqual(keeper.managed_allocations().count(), 1)
        self.assertEqual(keeper.managed_reservations().count(), 1)
        self.assertEqual(keeper.managed_reserved_slots().count(), 1)
