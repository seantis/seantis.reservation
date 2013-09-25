from datetime import datetime

from seantis.reservation.session import serialized
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.reports.monthly_report import monthly_report
from seantis.reservation.reports import GeneralReportParametersMixin

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

        today = (datetime(2013, 9, 25, 8), datetime(2013, 9, 25, 10))
        tomorrow = (datetime(2013, 9, 26, 8), datetime(2013, 9, 26, 10))

        sc.allocate(today, quota=2)
        sc.allocate(tomorrow, quota=1)

        sc.approve_reservation(sc.reserve(reservation_email, today))
        sc.approve_reservation(sc.reserve(reservation_email, today))
        sc.approve_reservation(sc.reserve(reservation_email, tomorrow))

        report = monthly_report(2013, 9, {resource.uuid(): resource})

        # one record for each day
        self.assertEqual(len(report), 2)

        # one resource for each day
        self.assertEqual(len(report[25]), 1)
        self.assertEqual(len(report[26]), 1)

        # two reservations on the first day
        self.assertEqual(len(report[25][resource.uuid()]['approved']), 2)

        # on reservation on the second day
        self.assertEqual(len(report[26][resource.uuid()]['approved']), 1)
