import mock
import pytz

from datetime import datetime, timedelta

from zope import i18n

from libres.context.session import serialized

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.reports import GeneralReportParametersMixin
from seantis.reservation.reports.monthly_report import monthly_report
from seantis.reservation.reports.latest_reservations import (
    human_date,
    latest_reservations
)

reservation_email = u'test@example.com'


class TestReports(IntegrationTestCase):

    def test_report_parameters_mixin_defaults(self):
        self.login_admin()

        mixin = GeneralReportParametersMixin()

        mixin.request = self.request()
        mixin.context = self.create_resource()

        self.assertEqual(mixin.uuids, [mixin.context.uuid()])

        self.assertEqual(mixin.hidden_statuses, [])
        self.assertEqual(mixin.reservations, [])
        self.assertEqual(mixin.hidden_resources, [])
        self.assertEqual(mixin.show_details, False)

    def test_report_parameters_mixin_build_url(self):
        self.login_admin()

        mixin = GeneralReportParametersMixin()

        mixin.request = self.request()
        mixin.context = self.create_resource()

        mixin.request.set('hide_status', ['pending'])
        mixin.request.set('show_details', '1')
        mixin.request.set('hide_resource', 'test')

        extras = [('foo', 'bar')]

        expected = (
            'http://nohost/plone/seantis-reservation-resource/test?'
            'show_details=1&hide_status=pending&hide_resource=test&uuid={}'
            '&foo=bar'
        ).format(mixin.context.uuid())

        mixin.__name__ = 'test'  # build_url expects this, usually set by grok
        self.assertEqual(mixin.build_url(extras), expected)

    @serialized
    def test_monthly_report_empty(self):
        self.login_admin()

        resource = self.create_resource()
        report = monthly_report(2013, 9, {resource.uuid(): resource})

        self.assertEqual(len(report), 0)

    @serialized
    def test_monthly_report_reservations(self):
        self.login_admin()

        resource = self.create_resource()
        sc = resource.scheduler()

        today = (datetime(2013, 9, 29, 8), datetime(2013, 9, 29, 10))
        tomorrow = (datetime(2013, 9, 30, 8), datetime(2013, 9, 30, 10))

        sc.allocate(today, quota=2)
        sc.allocate(tomorrow, quota=1)

        sc.approve_reservations(sc.reserve(reservation_email, today))
        sc.approve_reservations(sc.reserve(reservation_email, today))
        sc.approve_reservations(sc.reserve(reservation_email, tomorrow))

        report = monthly_report(2013, 9, {resource.uuid(): resource})

        # one record for each day
        self.assertEqual(len(report), 2)

        # one resource for each day
        self.assertEqual(len(report[29]), 1)
        self.assertEqual(len(report[30]), 1)

        # two reservations on the first day
        self.assertEqual(len(report[29][resource.uuid()]['approved']), 2)

        # on reservation on the second day
        self.assertEqual(len(report[30][resource.uuid()]['approved']), 1)

    @mock.patch('seantis.reservation.utils.utcnow')
    def test_latest_reservations_human_date(self, utcnow):
        translate = lambda text: i18n.translate(
            text, target_language='en', domain='seantis.reservation'
        )
        human = lambda date: translate(human_date(date))

        utc = lambda *args: datetime(*args).replace(tzinfo=pytz.utc)

        utcnow.return_value = utc(2013, 9, 27, 11, 0)

        self.assertEqual(
            human(utc(2013, 9, 27, 21, 0)),
            u'Today, at 21:00'
        )

        self.assertEqual(
            human(utc(2013, 9, 27, 10, 0)),
            u'Today, at 10:00'
        )

        self.assertEqual(
            human(utc(2013, 9, 27, 0, 0)),
            u'Today, at 00:00'
        )

        self.assertEqual(
            human(utc(2013, 9, 26, 23, 59)),
            u'Yesterday, at 23:59'
        )

        self.assertEqual(
            human(utc(2013, 9, 26, 0, 0)),
            u'Yesterday, at 00:00'
        )

        self.assertEqual(
            human(utc(2013, 9, 25, 23, 59)),
            u'2 days ago, at 23:59'
        )

        self.assertEqual(
            human(utc(2013, 9, 25, 00, 00)),
            u'2 days ago, at 00:00'
        )

        self.assertEqual(
            human(utc(2013, 9, 24, 23, 59)),
            u'3 days ago, at 23:59'
        )

        # does not really deal with the future, it's not a concern
        self.assertEqual(
            human(utc(2014, 9, 27, 21, 0)),
            u'Today, at 21:00'
        )

    @serialized
    def test_latest_reservations(self):

        self.login_admin()

        resource = self.create_resource()
        sc = resource.scheduler()

        today = (datetime(2013, 9, 25, 8), datetime(2013, 9, 25, 10))
        tomorrow = (datetime(2013, 9, 26, 8), datetime(2013, 9, 26, 10))

        sc.allocate(today, quota=1)
        sc.allocate(tomorrow, quota=1)

        sc.approve_reservations(sc.reserve(reservation_email, today))
        sc.approve_reservations(sc.reserve(reservation_email, tomorrow))

        now = datetime.utcnow().replace(tzinfo=pytz.utc)

        daterange = (now - timedelta(days=30), now)

        report = latest_reservations({resource.uuid(): resource}, daterange)
        self.assertEqual(len(report), 2)

        daterange = (now - timedelta(days=31), now - timedelta(seconds=60))

        report = latest_reservations({resource.uuid(): resource}, daterange)
        self.assertEqual(len(report), 0)
