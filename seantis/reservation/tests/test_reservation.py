from datetime import datetime
from seantis.reservation.models.reservation import Reservation
import unittest


class TestReservation(unittest.TestCase):

    def setUp(self):
        self.reservation = Reservation()
        self.reservation.start = datetime(2010, 1, 1, 9, 00)
        self.reservation.end = datetime(2010, 1, 1, 14, 15)

    def test_target_dates_recurrence(self):
        self.reservation.target_type = u'recurrence'
        self.reservation.rrule = 'RRULE:FREQ=DAILY;COUNT=3'

        dates = [(datetime(2010, 1, 1, 9, 00), datetime(2010, 1, 1, 14, 15)),
                 (datetime(2010, 1, 2, 9, 00), datetime(2010, 1, 2, 14, 15)),
                 (datetime(2010, 1, 3, 9, 00), datetime(2010, 1, 3, 14, 15))]

        self.assertListEqual(dates, self.reservation.target_dates())

    def test_target_dates_allocation(self):
        self.reservation.target_type = u'allocation'
        self.assertSequenceEqual([(self.reservation.start,
                                   self.reservation.end)],
                                 self.reservation.target_dates())

    def test_is_pending(self):
        self.reservation.status = 'pending'
        self.assertTrue(self.reservation.is_pending)

        self.reservation.status = 'approved'
        self.assertFalse(self.reservation.is_pending)
