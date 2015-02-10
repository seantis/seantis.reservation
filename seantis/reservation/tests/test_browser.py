import six
import json
import transaction

from datetime import timedelta, datetime
from itertools import chain

from zope.component import queryUtility, getUtility
from Products.CMFCore.interfaces import IPropertiesTool

from libres.context.session import serialized

from seantis.reservation import utils
from seantis.reservation.session import ILibresUtility
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

    def add_resource(
        self, name, description='', formsets=[], action=None, thank_you=''
    ):
        browser = self.admin_browser

        browser.open(self.infolder('/++add++seantis.reservation.resource'))
        browser.getControl('Name').value = name
        browser.getControl('Description').value = description
        browser.getControl('Thank you text').value = thank_you

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
        approve_manually=False,
        recurrence_start=None,
        recurrence_end=None,
        separately_reservable=False
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

        if recurrence_start and recurrence_end:
            browser.getControl('Daily').selected = True
            browser.set_date('form.widgets.recurrence_start', recurrence_start)
            browser.set_date('form.widgets.recurrence_end', recurrence_end)

            for day in ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'):
                browser.getControl(day).selected = True

            (
                browser.getControl('Separately reservable')
            ).selected = separately_reservable

        browser.getControl(
            'Manually approve reservation requests'
        ).selected = approve_manually

        browser.getControl('Allocate').click()
        assert 'There were some errors' not in browser.contents, """
            Failed to add allocation
        """

        return [resource, start, end]

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
        browser.getControl('Number of Reservations', index=0).value = '3'
        browser.getControl('Reserve').click()
        self.assertTrue(
            'number of reservations is higher than allowed' in browser.contents
        )
        self.assertEqual(
            '3', browser.getControl('Number of Reservations', index=0).value
        )

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
        browser.getControl('Number of Reservations', index=0).value = '3'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Number of Reservations', index=0).value = '3'

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
        browser.getControl('Number of Reservations', index=0).value = '1'
        browser.getControl('Reserve').click()
        browser.getControl('Reserve').click()
        self.assertFalse('Too many reservations' in browser.contents)

        # real reservations however do
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()
        self.assertFalse('Too many reservations' in browser.contents)

        browser.open(self.allocation_menu(*allocation)['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Number of Reservations', index=0).value = '1'
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

        # the datetime in the browsers cannot be swayed, it always is english
        self.assertTrue('Sep 13, 2013 11:00 AM - 12:00 PM' in browser.contents)

        browser.getLink('Remove').click()
        browser.open(self.infolder('/removal'))

        # the datetime in the browsers cannot be swayed, it always is english
        self.assertFalse(
            'Sep 13, 2013 11:00 AM - 12:00 PM' in browser.contents
        )

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

        # the datetime in the browsers cannot be swayed, it always is english
        self.assertTrue('Jun 21, 2013 01:00 PM - 05:00 PM' in browser.contents)

        browser.getControl('Approve').click()
        browser.open(menu['manage'])

        self.assertTrue('Revoke' in browser.contents)
        self.assertFalse('Approve' in browser.contents)

    def test_reservation_denial(self):

        browser = self.new_browser()
        browser.login_admin()

        start = datetime(2013, 6, 21, 13, 0)
        end = datetime(2013, 6, 21, 17, 0)

        self.add_resource('denial')

        allocation = ('denial', start, end)
        self.add_allocation(*allocation, approve_manually=True)
        menu = self.allocation_menu(*allocation)
        browser.open(menu['reserve'])

        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(menu['manage'])

        self.assertTrue('Approve' in browser.contents)
        self.assertTrue('Deny' in browser.contents)

        browser.getLink('Deny').click()
        self.assertTrue('Concerned Dates' in browser.contents)

        # the datetime in the browsers cannot be swayed, it always is english
        self.assertTrue('Jun 21, 2013 01:00 PM - 05:00 PM' in browser.contents)

        browser.getControl('Deny').click()
        self.assertTrue('Reservation denied' in browser.contents)

        browser.open(menu['manage'])
        self.assertFalse('Revoke' in browser.contents)
        self.assertFalse('Approve' in browser.contents)
        self.assertFalse('Deny' in browser.contents)

    def test_reserve_group(self):

        browser = self.admin_browser

        self.add_resource('group_reservation', action='publish')

        start = datetime(2014, 2, 25, 12, 00)
        end = datetime(2014, 2, 25, 15, 00)

        allocation = ['group_reservation', start, end]
        self.add_allocation(
            *allocation,
            recurrence_start=start.date(),
            recurrence_end=start.date() + timedelta(days=3)
        )
        menu = self.allocation_menu(*allocation)

        browser.open(menu['reserve'])

        self.assertEqual(browser.query('.result-time').length, 4)

        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()

        self.assertTrue('Your reservations' in browser.contents)

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

    def test_edit_email(self):
        browser = self.admin_browser

        self.add_resource('email')

        start = datetime(2013, 6, 27, 13, 37)
        end = datetime(2013, 6, 27, 17, 15)

        allocation = self.add_allocation('email', start, end)
        menu = self.allocation_menu(*allocation)

        browser.open(menu['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        # this can be verified on the manage-page
        browser.open(menu['manage'])
        self.assertTrue('test@example.com' in browser.contents)

        # the manager can at this point change the values
        browser.getLink('Edit Formdata').click()

        self.assertIn('test@example.com', browser.contents)

        browser.getControl('Email').value = 'invalid'
        browser.getControl('Save').click()

        self.assertIn('Invalid', browser.contents)

        browser.getControl('Email').value = 'asdf@asdf.com'
        browser.getControl('Save').click()

        browser.open(menu['manage'])
        self.assertIn('asdf@asdf.com', browser.contents)
        self.assertNotIn('test@example.com', browser.contents)

    def test_broken_formsets(self):

        browser = self.admin_browser

        self.add_formset(
            'one', [FormsetField('one', 'Text')], for_managers=False
        )
        self.add_formset(
            'two', [FormsetField('two', 'Text')], for_managers=False
        )

        self.add_resource(
            'broken', formsets=['one', 'two'], action='publish'
        )

        start = datetime(2013, 6, 27, 13, 37)
        end = datetime(2013, 6, 27, 17, 15)

        allocation = ['broken', start, end]
        self.add_allocation(*allocation)
        menu = self.allocation_menu(*allocation)

        browser.open(menu['reserve'])
        browser.getControl('Email').value = 'test@example.com'
        browser.getControl('one').value = 'Eins'
        browser.getControl('two').value = 'Zwei'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(menu['manage'])
        self.assertTrue('Eins' in browser.contents)
        self.assertTrue('Zwei' in browser.contents)

        browser.open(self.infolder('/broken/edit'))
        browser.getControl('two').selected = False
        browser.getControl('Save').click()

        browser.open(menu['manage'])
        browser.getLink('Edit Formdata').click()
        self.assertTrue('Unchangeable formdata found!' in browser.contents)
        self.assertFalse('<span>Eins</span>' in browser.contents)
        self.assertTrue('<span>Zwei</span>' in browser.contents)

        browser.open(self.infolder('/broken/edit'))
        browser.getControl('two').selected = True
        browser.getControl('Save').click()

        browser.open(menu['manage'])
        browser.getLink('Edit Formdata').click()
        self.assertFalse('Unchangeable formdata found!' in browser.contents)
        self.assertFalse('<span>Eins</span>' in browser.contents)
        self.assertFalse('<span>Zwei</span>' in browser.contents)

    @serialized
    def test_resource_removal(self):

        browser = self.admin_browser

        # have one resource with data during the run, to check that there's
        # no bleed over through the other tests

        self.add_resource('keeper')
        browser.open(self.infolder('/keeper/@@uuid'))
        uuid = six.text_type(browser.contents)

        keeper = getUtility(ILibresUtility).scheduler(uuid, 'UTC')

        self.assertEqual(keeper.managed_allocations().count(), 0)
        self.assertEqual(keeper.managed_reservations().count(), 0)
        self.assertEqual(keeper.managed_reserved_slots().count(), 0)

        dates = [
            datetime(2013, 7, 2, 10, 15), datetime(2013, 7, 2, 10, 30)
        ]
        keeper.allocate(dates, raster=15)

        token = keeper.reserve(u'test@example.com', dates)
        keeper.approve_reservations(token)

        # delete_confirmation will rollback, dropping all SQL statements
        transaction.commit()

        self.assertEqual(keeper.managed_allocations().count(), 1)
        self.assertEqual(keeper.managed_reservations().count(), 1)
        self.assertEqual(keeper.managed_reserved_slots().count(), 1)

        def run_test():
            self.add_resource('removal')
            browser.open(self.infolder('/removal/@@uuid'))
            uuid = six.text_type(browser.contents)

            scheduler = getUtility(ILibresUtility).scheduler(uuid, 'UTC')

            self.assertEqual(scheduler.managed_allocations().count(), 0)
            self.assertEqual(scheduler.managed_reservations().count(), 0)
            self.assertEqual(scheduler.managed_reserved_slots().count(), 0)

            scheduler.allocate(dates, raster=15)

            token = scheduler.reserve(u'test@example.com', dates)
            scheduler.approve_reservations(token)

            # delete_confirmation will rollback, dropping all SQL statements
            transaction.commit()

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

    @serialized
    def test_export_selection(self):
        browser = self.admin_browser

        self.add_resource('export')

        browser.open(self.infolder('/export/@@uuid'))
        uuid = browser.contents

        browser.open(
            self.infolder('/reservation-exports?uuid={}'.format(uuid))
        )

        self.assertIn('Reservation Export', browser.contents)
        browser.getControl(name='form.buttons.export').click()

        self.assertIn('uuid={}'.format(uuid), browser.url)
        self.assertIn('year=all', browser.url)
        self.assertIn('month=all', browser.url)

    @serialized
    def test_thank_you_page(self):
        browser = self.admin_browser

        self.add_resource('one', thank_you='<b>one thanks</b>')
        self.add_resource('two', thank_you='<b>two thanks</b>')
        self.add_resource('three', thank_you='')

        start, end = (
            datetime(2014, 6, 20, 15, 15), datetime(2014, 6, 20, 15, 30)
        )

        def reserve(resource):
            allocation = [resource, start, end]
            self.add_allocation(*allocation)

            menu = self.allocation_menu(*allocation)

            browser.open(menu['reserve'])
            browser.getControl('Email').value = 'test@example.org'
            browser.getControl('Reserve').click()

        map(reserve, ('one', 'two', 'three'))
        browser.getControl('Submit Reservations').click()

        self.assertIn('thank-you-for-reserving', browser.url)

        # one and two have thank you texts, so they show up
        self.assertIn('testfolder - one', browser.contents)
        self.assertIn('<b>one thanks</b>', browser.contents)

        self.assertIn('testfolder - two', browser.contents)
        self.assertIn('<b>two thanks</b>', browser.contents)

        # three doesn't, so it won't show up
        self.assertNotIn('testfolder - three', browser.contents)

    @serialized
    def test_pending_timespans(self):
        browser = self.admin_browser

        self.add_resource('manual')

        allocation = self.add_allocation(
            'manual',
            datetime(2014, 2, 25, 12, 00),
            datetime(2014, 2, 25, 15, 00),
            approve_manually=True
        )

        menu = self.allocation_menu(*allocation)

        # reserve this manually approved allocation
        browser.open(menu['reserve'])
        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        # as long as the reservation is not approved, there's no revoke
        # link for the dates in the reservation (because that would
        # require a separate mail message, would confuse the user and
        # would give the admins a way to willy-nilly change the users
        # reservation request which is what he wants approved
        # anyway - not some different thing)
        browser.open(menu['manage'])
        self.assertEqual(len(browser.query('.timespan-actions a')), 0)

        # approve it
        browser.getLink('Approve').click()
        browser.getControl('Approve').click()

        # ensure that the revoke is now being shown
        browser.open(menu['manage'])
        self.assertEqual(len(browser.query('.timespan-actions a')), 1)

    @serialized
    def test_remove_group_timespans(self):
        browser = self.admin_browser

        self.add_resource('group')

        start = datetime(2014, 2, 25, 12, 00)
        end = datetime(2014, 2, 25, 15, 00)

        allocation = self.add_allocation(
            'group', start, end,
            recurrence_start=start.date(),
            recurrence_end=start.date() + timedelta(days=3)
        )
        menu = self.allocation_menu(*allocation)

        browser.open(menu['reserve'])
        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(menu['manage'])

        # with this group reservation we should see three dates with one
        # revoke link only.
        self.assertEqual(len(browser.query('.timespan-actions a')), 1)
        self.assertEqual(len(browser.query('.timespan-dates')), 4)

        # clicking one will remove all dates
        browser.getLink('Revoke', index=1).click()
        self.assertEqual(len(browser.query('.limitedList > div')), 4)

        browser.getControl('Revoke').click()

        browser.open(menu['manage'])
        self.assertEqual(len(browser.query('.timespan-dates')), 0)

    @serialized
    def test_remove_timespans(self):
        browser = self.admin_browser

        self.add_resource('timespans')

        # create two allocations
        first = self.add_allocation(
            'timespans',
            datetime(2014, 2, 25, 12, 00),
            datetime(2014, 2, 25, 15, 00),
        )
        second = self.add_allocation(
            'timespans',
            datetime(2014, 2, 25, 16, 00),
            datetime(2014, 2, 25, 18, 00),
        )

        # reserve both in one go
        browser.open(self.infolder('/timespans/search'))

        browser.set_date('recurrence_start', datetime(2014, 2, 25))
        browser.set_date('recurrence_end', datetime(2014, 2, 25))

        browser.getControl(name='form.buttons.search').click()
        browser.getControl('Reserve selected').click()
        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        # while we're at it, make sure both manage views have the same dates
        manage_first = self.allocation_menu(*first)['manage']
        manage_second = self.allocation_menu(*second)['manage']

        browser.open(manage_first)
        self.assertIn('Feb 25, 2014 12:00 PM - 03:00 PM', browser.contents)
        self.assertIn('Feb 25, 2014 04:00 PM - 06:00 PM', browser.contents)

        browser.open(manage_second)
        self.assertIn('Feb 25, 2014 12:00 PM - 03:00 PM', browser.contents)
        self.assertIn('Feb 25, 2014 04:00 PM - 06:00 PM', browser.contents)

        # revoke the last date
        browser.getLink('Revoke', index=2).click()

        self.assertNotIn('12:00 PM - 03:00 PM', browser.contents)
        self.assertIn('04:00 PM - 06:00 PM', browser.contents)

        browser.getControl('Revoke').click()

        # ensure the date is gone
        browser.open(manage_first)
        self.assertIn('12:00 PM - 03:00 PM', browser.contents)
        self.assertNotIn('04:00 PM - 06:00 PM', browser.contents)

        # the second allocation now has no link to any reservations
        browser.open(manage_second)
        self.assertNotIn('12:00 PM - 03:00 PM', browser.contents)
        self.assertNotIn('04:00 PM - 06:00 PM', browser.contents)

        # remove the second date, ensuring that the whole reservation is gone
        browser.open(manage_first)
        browser.getLink('Revoke', index=1).click()
        self.assertIn('12:00 PM - 03:00 PM', browser.contents)

        browser.getControl('Revoke').click()

        browser.open(manage_first)
        self.assertNotIn('12:00 PM - 03:00 PM', browser.contents)
        self.assertNotIn('04:00 PM - 06:00 PM', browser.contents)

    @serialized
    def test_search_specific_time(self):
        # make sure that a search for a specific timerange on a partly
        # available allocation only returns the availability in this timerange
        browser = self.admin_browser

        self.add_resource('resource')

        daterange = (
            datetime(2014, 8, 20, 8, 00), datetime(2014, 8, 20, 10, 00)
        )

        allocation = ['resource', daterange[0], daterange[1]]
        self.add_allocation(*allocation, partly_available=True)

        # reserve 08:00 - 09:00
        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 21)
        )
        browser.getControl('Start time').value = '08:00 AM'
        browser.getControl('End time').value = '09:00 AM'
        browser.getControl('Available only').selected = True

        browser.getControl(name='form.buttons.search').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('100%', browser.contents)
        self.assertIn('event-available', browser.contents)

        browser.getControl('Reserve selected').click()

        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()

        # now search for 08:00 - 09:00, which should yield 0% (unavailable)
        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 21)
        )
        browser.getControl('Start time').value = '08:00 AM'
        browser.getControl('End time').value = '09:00 AM'
        browser.getControl('Available only').selected = False

        browser.getControl(name='form.buttons.search').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('0%', browser.contents)
        self.assertNotIn('100%', browser.contents)
        self.assertIn('event-unavailable', browser.contents)

        # now try to search for 09:00 - 10:00, which should yield 100%
        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 21)
        )
        browser.getControl('Start time').value = '09:00 AM'
        browser.getControl('End time').value = '10:00 AM'
        browser.getControl('Available only').selected = True

        browser.getControl(name='form.buttons.search').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('100%', browser.contents)
        self.assertIn('event-available', browser.contents)

    @serialized
    def test_search_and_reserve(self):
        browser = self.admin_browser

        self.add_resource('resource')

        dates = [
            (datetime(2014, 8, 20, 15, 00), datetime(2014, 8, 20, 16, 00)),
            (datetime(2014, 8, 21, 15, 00), datetime(2014, 8, 21, 16, 00)),
            (datetime(2014, 8, 22, 15, 00), datetime(2014, 8, 22, 16, 00)),
        ]

        allocations = [['resource', s, e] for s, e in dates]

        for allocation in allocations:
            self.add_allocation(*allocation)

        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 21)
        )

        # these values should be passed to the selection form
        browser.getControl('Start time').value = '10:00 AM'
        browser.getControl('End time').value = '10:00 PM'
        browser.getControl('Spots').value = '1'

        browser.getControl(name='form.buttons.search').click()
        self.assertNotIn('No results found', browser.contents)
        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)
        self.assertNotIn('Aug 22, 2014', browser.contents)

        # all allocations in the results are available, so they are preselected
        chks = browser.query('input[name="allocation_id"][checked="checked"]')
        self.assertEqual(len(chks), 2)

        browser.getControl('Reserve selected').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)
        self.assertNotIn('Aug 22, 2014', browser.contents)

        self.assertEqual(
            browser.query('#form-widgets-start_time').val(), '10:00 AM'
        )
        self.assertEqual(
            browser.query('#form-widgets-end_time').val(), '10:00 PM'
        )
        self.assertEqual(browser.query('#form-widgets-quota').val(), '1')

        # submit an invalid reservation and ensure that everything remains
        browser.getControl('Reserve').click()
        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)
        self.assertNotIn('Aug 22, 2014', browser.contents)

        self.assertEqual(
            browser.query('#form-widgets-start_time').val(), '10:00 AM'
        )
        self.assertEqual(
            browser.query('#form-widgets-end_time').val(), '10:00 PM'
        )
        self.assertEqual(browser.query('#form-widgets-quota').val(), '1')

        # go ahead
        browser.getControl('Email').value = 'info@example.org'
        browser.getControl('Reserve').click()

        # no try the search again, but include all dates
        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 22)
        )

        browser.getControl(name='form.buttons.search').click()
        self.assertNotIn('No results found', browser.contents)
        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)
        self.assertIn('Aug 22, 2014', browser.contents)

        # this time only one allocation is still available, which is reflected
        # in the state of the checkboxes
        chks = browser.query('input[name="allocation_id"][checked="checked"]')
        self.assertEqual(len(chks), 1)

    @serialized
    def test_change_time(self):
        browser = self.admin_browser

        self.add_resource('resource')

        allocations = [
            self.add_allocation(
                'resource',
                datetime(2014, 8, 20, 15, 00),
                datetime(2014, 8, 20, 16, 00),
                partly_available=True
            ),
            self.add_allocation(
                'resource',
                datetime(2014, 8, 21, 15, 00),
                datetime(2014, 8, 21, 16, 00),
                partly_available=False
            ),
        ]

        # reserve both allocations at once to see them in the same manage view
        browser.open(self.infolder('/resource/search'))
        browser.set_date(
            'form.widgets.recurrence_start', datetime(2014, 8, 20)
        )
        browser.set_date(
            'form.widgets.recurrence_end', datetime(2014, 8, 21)
        )
        browser.getControl(name='form.buttons.search').click()
        browser.getControl('Reserve selected').click()
        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        # two revoke links + one change link == 3
        browser.open(self.allocation_menu(*allocations[0])['manage'])

        self.assertEqual(browser.query('.timespan-actions a').length, 3)
        self.assertIn('Aug 20, 2014 03:00 PM - 04:00 PM', browser.contents)

        browser.getLink('Change').click()
        browser.getControl('Start').value = '03:30 PM'
        browser.getControl('Save').click()

        browser.open(self.allocation_menu(*allocations[0])['manage'])
        self.assertIn('Aug 20, 2014 03:30 PM - 04:00 PM', browser.contents)

    @serialized
    def test_remove_link_admin_only(self):
        browser = self.admin_browser

        self.add_resource('resource')

        self.add_allocation(
            'resource',
            datetime(2014, 8, 20, 15, 00),
            datetime(2014, 8, 20, 16, 00)
        ),
        self.add_allocation(
            'resource',
            datetime(2014, 8, 21, 15, 00),
            datetime(2014, 8, 21, 16, 00)
        )

        browser.open(self.infolder('/resource/search'))
        browser.set_date('recurrence_start', datetime(2014, 8, 20))
        browser.set_date('recurrence_end', datetime(2014, 8, 21))
        browser.getControl(name='form.buttons.search').click()
        self.assertIn('Delete selected', browser.contents)

        anonymous = self.new_browser()
        anonymous.open(self.infolder('/resource/search'))
        anonymous.set_date('recurrence_start', datetime(2014, 8, 20))
        anonymous.set_date('recurrence_end', datetime(2014, 8, 21))
        anonymous.getControl(name='form.buttons.search').click()
        self.assertNotIn('Delete selected', anonymous.contents)

    @serialized
    def test_remove_multiple_allocations(self):
        browser = self.admin_browser

        self.add_resource('resource')

        self.add_allocation(
            'resource',
            datetime(2014, 8, 20, 15, 00),
            datetime(2014, 8, 20, 16, 00)
        )
        self.add_allocation(
            'resource',
            datetime(2014, 8, 21, 15, 00),
            datetime(2014, 8, 21, 16, 00)
        )

        browser.open(self.infolder('/resource/search'))
        browser.set_date('recurrence_start', datetime(2014, 8, 20))
        browser.set_date('recurrence_end', datetime(2014, 8, 21))
        browser.getControl(name='form.buttons.search').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)

        browser.getLink('Delete selected').click()

        self.assertIn('Aug 20, 2014', browser.contents)
        self.assertIn('Aug 21, 2014', browser.contents)

        browser.getControl('Delete').click()

        browser.open(self.infolder('/resource/search'))
        browser.set_date('recurrence_start', datetime(2014, 8, 20))
        browser.set_date('recurrence_end', datetime(2014, 8, 21))
        browser.getControl(name='form.buttons.search').click()

        self.assertNotIn('Aug 20, 2014', browser.contents)
        self.assertNotIn('Aug 21, 2014', browser.contents)

    @serialized
    def test_remove_multiple_reserved_allocations(self):
        browser = self.admin_browser

        self.add_resource('resource')

        self.add_allocation(
            'resource',
            datetime(2014, 8, 20, 15, 00),
            datetime(2014, 8, 20, 16, 00),
            quota=2
        )
        self.add_allocation(
            'resource',
            datetime(2014, 8, 21, 15, 00),
            datetime(2014, 8, 21, 16, 00),
            quota=2
        )

        browser.open(self.infolder('/resource/search'))
        browser.set_date('recurrence_start', datetime(2014, 8, 20))
        browser.set_date('recurrence_end', datetime(2014, 8, 21))
        browser.getControl(name='form.buttons.search').click()

        browser.getControl('Reserve selected').click()
        browser.getControl('Email').value = 'test@example.org'
        browser.getControl('Reserve').click()
        browser.getControl('Submit Reservations').click()

        browser.open(self.infolder('/resource/search'))
        browser.set_date('recurrence_start', datetime(2014, 8, 20))
        browser.set_date('recurrence_end', datetime(2014, 8, 21))
        browser.getControl(name='form.buttons.search').click()

        browser.getLink('Delete selected').click()
        browser.getControl('Delete').click()

        self.assertIn('An existing reservation', browser.contents)
