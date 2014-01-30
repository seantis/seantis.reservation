from datetime import datetime, timedelta, date

from seantis.reservation import utils
from seantis.reservation.tests import IntegrationTestCase


class UtilsTestCase(IntegrationTestCase):

    def test_pairs(self):
        one = ('aa', 'bb', 'cc', 'dd')
        two = (('aa', 'bb'), ('cc', 'dd'))

        self.assertEqual(utils.pairs(one), utils.pairs(two))

    def test_as_human_readable_string(self):
        self.assertEqual(
            utils.as_human_readable_string(datetime(2012, 1, 12)),
            '12.01.2012 00:00'
        )

        self.assertEqual(
            utils.as_human_readable_string(datetime(1889, 5, 12, 12)),
            '12.05.1889 12:00'
        )

        self.assertEqual(
            utils.as_human_readable_string(datetime(3, 5, 12, 13, 3)),
            '12.05.0003 13:03'
        )

        self.assertEqual(
            utils.as_human_readable_string(date(2012, 1, 12)),
            '12.01.2012'
        )

        self.assertEqual(
            utils.as_human_readable_string(date(1889, 5, 12)),
            '12.05.1889'
        )

        self.assertEqual(
            utils.as_human_readable_string(date(3, 5, 12)),
            '12.05.0003'
        )

        self.assertEqual(
            utils.as_human_readable_string(None), u''
        )

        self.assertEqual(
            utils.as_human_readable_string([True, False]),
            u'Yes, No'
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
            utils.unite(
                [1, 1, 1, 2, 2], lambda last, current: last == current
            ),
            [[1, 1, 1], [2, 2]]
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
