from datetime import datetime

from seantis.reservation.session import serialized
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.reports.monthly_report import monthly_report

reservation_email = u'test@example.com'

class TestReports(IntegrationTestCase):

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
