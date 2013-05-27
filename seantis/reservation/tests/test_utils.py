from datetime import datetime

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
