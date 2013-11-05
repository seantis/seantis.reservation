from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from seantis.reservation import utils
from seantis.reservation.tests import IntegrationTestCase


class UtilsTestCase(IntegrationTestCase):

    def test_pairs(self):
        one = ('aa', 'bb', 'cc', 'dd')
        two = (('aa', 'bb'), ('cc', 'dd'))

        self.assertEqual(utils.pairs(one), utils.pairs(two))

    def test_decoded_for_displays(self):
        self.assertEqual(
            utils.decode_for_display(datetime(year=2012, month=1, day=12)),
            '12.01.2012 00:00'
        )

        self.assertEqual(
            utils.decode_for_display(datetime(1889, 5, 12, 12)),
            '12.05.1889 12:00'
        )

        self.assertEqual(
            utils.decode_for_display(datetime(3, 5, 12, 13, 3)),
            '12.05.0003 13:03'
        )

        self.assertEqual(
            utils.decode_for_display(date(2012, 1, 12)),
            '12.01.2012'
        )

        self.assertEqual(
            utils.decode_for_display(date(1889, 5, 12)),
            '12.05.1889'
        )

        self.assertEqual(
            utils.decode_for_display(date(3, 5, 12)),
            '12.05.0003'
        )

    def test_align_dates(self):
        self.assertEqual(
            utils.align_date_to_day(datetime(2012, 1, 1, 0, 0), 'down'),
            datetime(2012, 1, 1, 0, 0)
        )

        self.assertEqual(
            utils.align_date_to_day(datetime(2012, 1, 1, 0, 0), 'up'),
            datetime(2012, 1, 1, 23, 59, 59, 999999)
        )

        self.assertEqual(
            utils.align_date_to_day(datetime(2012, 1, 1, 0, 1), 'down'),
            datetime(2012, 1, 1, 0, 0)
        )

        self.assertEqual(
            utils.align_date_to_day(datetime(2012, 1, 1, 0, 1), 'up'),
            datetime(2012, 1, 1, 23, 59, 59, 999999)
        )

        self.assertEqual(
            utils.align_date_to_day(
                datetime(2012, 1, 1, 23, 59, 59, 999999), 'down'
            ),
            datetime(2012, 1, 1, 0, 0)
        )

        self.assertEqual(
            utils.align_date_to_day(
                datetime(2012, 1, 1, 23, 59, 59, 999999), 'up'
            ),
            datetime(2012, 1, 1, 23, 59, 59, 999999)
        )

        self.assertEqual(
            utils.align_range_to_day(
                datetime(2012, 1, 2, 0, 0),
                datetime(2012, 1, 2, 0, 0)
            ),
            (
                datetime(2012, 1, 2, 0, 0),
                datetime(2012, 1, 2, 23, 59, 59, 999999)
            )
        )

        self.assertEqual(
            utils.align_range_to_day(
                datetime(2012, 1, 2, 0, 0),
                datetime(2012, 1, 3, 0, 0)
            ),
            (
                datetime(2012, 1, 2, 0, 0),
                datetime(2012, 1, 3, 23, 59, 59, 999999)
            )
        )

    def test_request_id_as_int(self):
        self.assertEqual(-1, utils.request_id_as_int('-1'))
        self.assertEqual(0, utils.request_id_as_int('not an int at all'))
        self.assertEqual(0, utils.request_id_as_int(None))
        self.assertEqual(0, utils.request_id_as_int('0'))
        self.assertEqual(1, utils.request_id_as_int(1))
        self.assertEqual(99, utils.request_id_as_int('99'))

    def test_whole_day(self):
        self.assertTrue(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 2)
            )
        )
        self.assertFalse(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 1)
            )
        )
        self.assertTrue(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 2) - timedelta(seconds=1)
            )
        )
        self.assertFalse(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 2) - timedelta(seconds=2)
            )
        )
        self.assertTrue(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 3)
            )
        )
        self.assertTrue(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 3) - timedelta(seconds=1)
            )
        )
        self.assertFalse(
            utils.whole_day(
                datetime(2012, 1, 1),
                datetime(2012, 1, 3) - timedelta(seconds=2)
            )
        )


    def test_unite(self):
        self.assertEqual(
            utils.unite([1, 1, 1, 2, 2], lambda last, current: last == current),
            [[1,1,1], [2, 2]]
        )

        united = utils.United(lambda last, current: last == current)

        united.append(1)
        self.assertEqual(united.groups, [[1]])

        united.append(1)
        self.assertEqual(united.groups, [[1, 1]])

        united.append(2)
        self.assertEqual(united.groups, [[1, 1], [2]])

        united.append(1)
        self.assertEqual(united.groups, [[1, 1], [2], [1]])

    def test_unite_dates(self):
        self.assertEqual(
            list(utils.unite_dates([
                (datetime(2012, 1, 1), datetime(2012, 1, 2))
            ])),
            [
                (datetime(2012, 1, 1), datetime(2012, 1, 2))
            ]
        )
        self.assertEqual(
            list(utils.unite_dates([
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 3), datetime(2012, 1, 4))
            ])),
            [
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 3), datetime(2012, 1, 4))
            ]
        )
        self.assertEqual(
            list(utils.unite_dates([
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 2), datetime(2012, 1, 3)),
                (datetime(2012, 1, 4), datetime(2012, 1, 5)),
            ])),
            [
                (datetime(2012, 1, 1), datetime(2012, 1, 3)),
                (datetime(2012, 1, 4), datetime(2012, 1, 5)),
            ]
        )
        self.assertEqual(
            list(utils.unite_dates([
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 3), datetime(2012, 1, 4)),
                (datetime(2012, 1, 4), datetime(2012, 1, 5)),
            ])),
            [
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 3), datetime(2012, 1, 5)),
            ]
        )
        self.assertEqual(
            list(utils.unite_dates([
                (datetime(2012, 1, 1), datetime(2012, 1, 2)),
                (datetime(2012, 1, 2), datetime(2012, 1, 3)),
                (datetime(2012, 1, 10), datetime(2012, 1, 11)),
                (datetime(2012, 1, 3), datetime(2012, 1, 4)),
                (datetime(2012, 1, 11), datetime(2012, 1, 12)),
            ])),
            [
                (datetime(2012, 1, 1), datetime(2012, 1, 4)),
                (datetime(2012, 1, 10), datetime(2012, 1, 12)),
            ]
        )

    def test_get_dates_document_recurrence_exdate_bug(self):
        """Document a bug(-fix) where exdates for recurrences were not applied
        correctly.

        """
        recurrence = u'RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL=20140402T000000'\
                     u'\r\nEXDATE:20140304T000000'
        data = {'start_time': time(13, 0),
                'recurrence': recurrence,
                'end_time': time(16, 30),
                'day': date(2014, 2, 18)}

        dates = utils.get_dates(data)
        self.assertEqual(3, len(dates))

        expected = [(datetime(2014, 2, 18, 13), datetime(2014, 2, 18, 16, 30)),
                    (datetime(2014, 3, 18, 13), datetime(2014, 3, 18, 16, 30)),
                    (datetime(2014, 4, 1, 13), datetime(2014, 4, 1, 16, 30))]
        self.assertListEqual(expected, dates)

    def test_as_machine_time(self):
        self.assertEqual(
            (time(1), time(2, 59, 59, 999999)),
            utils.as_machine_time(1, 3)
        )

        self.assertEqual(
            (time(0), time(23, 59, 59, 999999)),
            utils.as_machine_time(0, 24)
        )

        self.assertRaises(AssertionError, utils.as_machine_time, 0, 0)
