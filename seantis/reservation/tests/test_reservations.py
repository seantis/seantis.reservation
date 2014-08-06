# -*- coding: utf-8 -*-

from datetime import date

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.reservations import combine_reservations


class TestReservations(IntegrationTestCase):

    def test_combined_reservations(self):

        class Reservation(object):

            def __init__(self, id, token, timespans, data):
                self.id = id
                self.data = data
                self.token = token
                self._timespans = timespans

            def timespans(self):
                return self._timespans

        reservations = [
            Reservation(1, 'a', [
                (date(2014, 1, 1), date(2014, 1, 1)),
                (date(2014, 1, 2), date(2014, 1, 2)),
                (date(2014, 1, 3), date(2014, 1, 3)),
            ], data={'id': 1}),
            Reservation(2, 'b', [
                (date(2015, 1, 1), date(2015, 1, 1)),
                (date(2015, 1, 2), date(2015, 1, 2)),
            ], data={'id': 2}),

            Reservation(3, 'b', [
                (date(2015, 1, 3), date(2015, 1, 3)),
            ], data={'id': 3}),
        ]

        combined = list(combine_reservations(reservations))
        self.assertEqual(len(combined), 2)

        a, b = combined
        self.assertEqual(a.reservation.data['id'], 1)
        self.assertEqual(b.reservation.data['id'], 2)

        self.assertEqual(a.timespans(), [
            (date(2014, 1, 1), date(2014, 1, 1)),
            (date(2014, 1, 2), date(2014, 1, 2)),
            (date(2014, 1, 3), date(2014, 1, 3)),
        ])

        self.assertEqual(b.timespans(), [
            (date(2015, 1, 1), date(2015, 1, 1)),
            (date(2015, 1, 2), date(2015, 1, 2)),
            (date(2015, 1, 3), date(2015, 1, 3)),
        ])
