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
