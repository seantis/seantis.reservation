from datetime import datetime

from seantis.reservation.reports.monthly_report import MonthlyReportView
from seantis.reservation.tests import IntegrationTestCase


class TestMonthlyReport(IntegrationTestCase):

    def setUp(self):
        super(TestMonthlyReport, self).setUp()

        self.portal = self.layer['portal']
        self.login_manager()
        self.resource = self.create_resource()
        self.resource.first_hour = 9
        self.resource.last_hour = 17

        self.view = MonthlyReportView(self.resource, self.request())

    def test_merged_divisions_spans_two_rows(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 0),
                                        end=datetime(2010, 1, 1, 11, 0)))
        # 9-11 (colspan: 2), 11-12, ..., 16-17
        self.assertEqual(7, len(results))
        entry = results[0]
        self.assertEqual(0, entry['left'])
        self.assertEqual(0, entry['right'])
        self.assertEqual(2, entry['span'])

    def test_merged_divisions_exact_cell_size(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 0),
                                        end=datetime(2010, 1, 1, 10, 0)))
        # 9-10, 10-11, ..., 16-17
        self.assertEqual(8, len(results))
        entry = results[0]
        self.assertEqual(0, entry['left'])
        self.assertEqual(0, entry['right'])
        self.assertEqual(1, entry['span'])

    def test_merged_divisions_left_margin(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 30),
                                        end=datetime(2010, 1, 1, 10, 0)))
        # 9-10, 10-11, ..., 16-17
        self.assertEqual(8, len(results))
        entry = results[0]
        self.assertEqual(50, entry['left'])
        self.assertEqual(0, entry['right'])
        self.assertEqual(1, entry['span'])

    def test_merged_divisions_right_margin(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 00),
                                        end=datetime(2010, 1, 1, 9, 45)))
        # 9-10, 10-11, ..., 16-17
        self.assertEqual(8, len(results))
        entry = results[0]
        self.assertEqual(0, entry['left'])
        self.assertEqual(25, entry['right'])
        self.assertEqual(1, entry['span'])

    def test_merged_divisions_both_margin(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 15),
                                        end=datetime(2010, 1, 1, 9, 45)))
        # 9-10, 10-11, ..., 16-17
        self.assertEqual(8, len(results))
        entry = results[0]
        self.assertEqual(25, entry['left'])
        self.assertEqual(25, entry['right'])
        self.assertEqual(1, entry['span'])

    def test_merged_divisions_both_margin_spanning_three_rows(self):
        results = self.view.merged_divisions(dict(
                                        start=datetime(2010, 1, 1, 9, 15),
                                        end=datetime(2010, 1, 1, 11, 45)))
        # 9-12, 12-13, ..., 16-17
        self.assertEqual(6, len(results))
        entry = results[0]
        self.assertAlmostEqual(100 / 12.0, entry['left'])
        self.assertAlmostEqual(100 / 12.0, entry['right'])
        self.assertEqual(3, entry['span'])
