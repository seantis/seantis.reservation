# -*- coding: utf-8 -*-
from datetime import datetime

from Acquisition import aq_base

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation import utils
from seantis.reservation.session import serialized
from seantis.reservation import exports


class TestExports(IntegrationTestCase):

    @serialized
    def test_reservations_export(self):
        self.login_manager()

        resource = self.create_resource()
        sc = resource.scheduler()

        start = datetime(2012, 2, 1, 12, 0)
        end = datetime(2012, 2, 1, 16, 0)
        dates = (start, end)

        reservation_email = u'test@example.com'
        sc.allocate(dates, approve_manually=False, quota=2)[0]

        token1 = sc.reserve(
            reservation_email, dates,
            data=utils.mock_data_dictionary(
                {
                    'stop': u'hammertime!',
                    'bust': u'a move!'
                }
            )
        )

        token2 = sc.reserve(
            reservation_email, dates,
            data=utils.mock_data_dictionary(
                {
                    'never': u'gonna',
                    'give': u'you up'
                }
            )
        )

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en'
        )

        self.assertEqual(len(dataset), 2)
        self.assertEqual(len(dataset.headers), 9 + 4)

        self.assertEqual(dataset.dict[0]['Token'], utils.string_uuid(token1))
        self.assertEqual(dataset.dict[0]['Mocktest.stop'], u'hammertime!')
        self.assertEqual(dataset.dict[0]['Mocktest.bust'], u'a move!')
        self.assertEqual(dataset.dict[0]['Mocktest.never'], None)
        self.assertEqual(dataset.dict[0]['Mocktest.give'], None)

        self.assertEqual(dataset.dict[1]['Token'], utils.string_uuid(token2))
        self.assertEqual(dataset.dict[1]['Mocktest.stop'], None)
        self.assertEqual(dataset.dict[1]['Mocktest.bust'], None)
        self.assertEqual(dataset.dict[1]['Mocktest.never'], u'gonna')
        self.assertEqual(dataset.dict[1]['Mocktest.give'], u'you up')

        # just make sure these don't raise exceptions
        dataset.xls
        dataset.json
        dataset.csv

    @serialized
    def test_reservations_export_title(self):
        self.login_manager()

        resource = self.create_resource()
        sc = resource.scheduler()

        start = datetime(2012, 2, 1, 12, 0)
        end = datetime(2012, 2, 1, 16, 0)
        dates = (start, end)

        reservation_email = u'test@example.com'
        sc.allocate(dates, approve_manually=False, quota=2)[0]

        sc.reserve(reservation_email, dates)

        # with title
        resource.aq_inner.aq_parent.title = 'testtitel'

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en'
        )

        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset[0][0], 'testtitel')

        # without title
        resource = aq_base(resource)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en'
        )

        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset[0][0], None)
