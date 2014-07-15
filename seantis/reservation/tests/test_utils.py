from datetime import datetime, timedelta, date

from seantis.reservation import utils
from seantis.reservation import settings
from seantis.reservation.tests import IntegrationTestCase


class UtilsTestCase(IntegrationTestCase):

    def test_pairs(self):
        one = ('aa', 'bb', 'cc', 'dd')
        two = (('aa', 'bb'), ('cc', 'dd'))

        self.assertEqual(utils.pairs(one), utils.pairs(two))

    def test_event_class(self):
        self.assertEqual(utils.event_class(100), 'event-available')
        self.assertEqual(utils.event_class(75), 'event-available')
        self.assertEqual(utils.event_class(1), 'event-partly-available')
        self.assertEqual(utils.event_class(0), 'event-unavailable')

        settings.set('available_threshold', 100)
        settings.set('partly_available_threshold', 1)

        self.assertEqual(utils.event_class(100), 'event-available')
        self.assertEqual(utils.event_class(99), 'event-partly-available')
        self.assertEqual(utils.event_class(1), 'event-partly-available')
        self.assertEqual(utils.event_class(0), 'event-unavailable')

    def test_merge_additional_data(self):
        base, extra = {}, {}

        self.assertEqual(utils.merge_data_dictionaries(base, extra), {})

        base = {
            'form': {
                'desc': "Base Description",
                'interface': "Base Interface",
                'values': [
                    {
                        'key': "one",
                        'value': "eins",
                        'desc': "one == eins"
                    },
                    {
                        'key': "two",
                        'value': "zwei",
                        'desc': "two == zwei"
                    },
                ]
            }
        }

        extra = {
            'form': {
                'desc': "Extra Description",
                'interface': "Extra Interface",
                'values': [
                    {
                        'key': "two",
                        'value': "deux",
                        'desc': "two == deux"
                    },
                    {
                        'key': "three",
                        'value': "drei",
                        'desc': "three == drei"
                    },
                ]
            },
            'another_form': {}
        }

        merged = {
            'form': {
                'desc': "Extra Description",
                'interface': "Extra Interface",
                'values': [
                    {
                        'key': "one",
                        'value': "eins",
                        'desc': "one == eins"
                    },
                    {
                        'key': "two",
                        'value': "deux",
                        'desc': "two == deux"
                    },
                    {
                        'key': "three",
                        'value': "drei",
                        'desc': "three == drei"
                    },
                ]
            },
            'another_form': {}
        }

        self.maxDiff = None
        actual_merged = utils.merge_data_dictionaries(base, extra)

        self.assertEqual(merged.keys(), actual_merged.keys())
        self.assertEqual(
            merged['form']['values'], actual_merged['form']['values']
        )
        self.assertEqual(merged['form'], actual_merged['form'])

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
