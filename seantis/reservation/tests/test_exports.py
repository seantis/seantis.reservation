# -*- coding: utf-8 -*-
from datetime import datetime

from Acquisition import aq_base

from libres.context.session import serialized

from pytz import timezone
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation import utils
from seantis.reservation import exports
from seantis.reservation.export import ExportView, prepare_record


class TestExports(IntegrationTestCase):

    @serialized
    def test_reservations_export(self):
        self.login_manager()

        resource = self.create_resource()
        sc = resource.scheduler()

        start = datetime(2012, 2, 1, 12, 0, tzinfo=timezone('UTC'))
        end = datetime(2012, 2, 1, 16, 0, tzinfo=timezone('UTC'))
        some_date = datetime(2014, 1, 30, 13, 37, tzinfo=timezone('UTC'))
        dates = (start, end)

        sc.allocate(dates, approve_manually=False, quota=2)[0]

        token1 = sc.reserve(
            u'a@example.com', dates,
            data=utils.mock_data_dictionary(
                {
                    'stop': u'hammertime!',
                    'bust': u'a move!',
                    'when': some_date
                }
            )
        )

        token2 = sc.reserve(
            u'b@example.com', dates,
            data=utils.mock_data_dictionary(
                {
                    'never': u'gonna',
                    'give': u'you up',
                    'when': some_date
                }
            )
        )

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', 'all', 'all'
        )

        self.assertEqual(len(dataset), 2)

        existing_columns = 11
        token_1_unique = 2
        token_2_unique = 2
        token_common = 1

        self.assertEqual(
            len(dataset.headers),
            existing_columns + token_1_unique + token_2_unique + token_common
        )

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

        self.assertEqual(dataset.dict[0]['Start'], start)
        self.assertEqual(dataset.dict[1]['Start'], start)
        self.assertEqual(dataset.dict[0]['End'], end)
        self.assertEqual(dataset.dict[1]['End'], end)

        self.assertEqual(dataset.dict[0]['Mocktest.when'], some_date)
        self.assertEqual(dataset.dict[1]['Mocktest.when'], some_date)

        # just make sure these don't raise exceptions
        for format in ('xls', 'xlsx', 'json', 'csv'):
            transform_record = lambda r: prepare_record(r, format)
            dataset = exports.reservations.dataset(
                {resource.uuid(): resource},
                'en', 'all', 'all', transform_record
            )
            getattr(dataset, format)

    @serialized
    def test_reservations_export_date_filter(self):
        self.login_manager()

        resource = self.create_resource()
        sc = resource.scheduler()

        this_year = (
            datetime(2013, 1, 1, 12, 0), datetime(2013, 1, 1, 13, 0)
        )

        next_year = (
            datetime(2014, 1, 1, 12, 0), datetime(2014, 1, 1, 13, 0)
        )

        reservation_email = u'test@example.com'
        sc.allocate(this_year, approve_manually=False)
        sc.allocate(next_year, approve_manually=False)

        sc.reserve(reservation_email, this_year)
        sc.reserve(reservation_email, next_year)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', year='all', month='all'
        )
        self.assertEqual(len(dataset), 2)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', year='all', month='1'
        )
        self.assertEqual(len(dataset), 2)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', year='2013', month='all'
        )
        self.assertEqual(len(dataset), 1)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', year='2010', month='all'
        )
        self.assertEqual(len(dataset), 0)

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
            {resource.uuid(): resource}, 'en', 'all', 'all'
        )

        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset[0][0], 'testtitel')

        # without title
        resource = aq_base(resource)

        dataset = exports.reservations.dataset(
            {resource.uuid(): resource}, 'en', 'all', 'all'
        )

        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset[0][0], None)

    def test_export_view(self):

        class MyExportView(ExportView):
            pass

        view = MyExportView(self.portal, self.request())

        self.assertRaises(NotImplementedError, lambda: view.content_type)
        self.assertRaises(NotImplementedError, lambda: view.file_extension)

        view.request['source'] = 'reservations'
        self.assertTrue(hasattr(view.source, '__call__'))

        view.request['source'] = 'united-reservations'
        self.assertTrue(hasattr(view.source, '__call__'))

        view.request['source'] = 'nonexistant'
        self.assertRaises(NotImplementedError, lambda: view.source)

        class MyJsonExportView(ExportView):
            content_type = 'application/json'
            file_extension = 'json'

        view = MyJsonExportView(self.portal, self.request())

        view.request['source'] = 'reservations'
        self.assertEqual('[]', view.render())

        response = view.request.RESPONSE
        self.assertEqual(response.headers['content-length'], '2')
        self.assertEqual(
            response.headers['content-disposition'],
            'filename="Plone site.Reservations (Normal).json"'
        )
        self.assertEqual(
            response.headers['content-type'], 'application/json;charset=utf-8'
        )
