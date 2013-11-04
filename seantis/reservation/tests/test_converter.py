from datetime import time

from z3c.form.browser.text import TextWidget
from z3c.form.converter import FormatterValidationError
from z3c.form.testing import TestRequest
from zope import schema
from zope.i18n.locales import locales

from seantis.reservation.converter import FriendlyTimeDataConverter
from seantis.reservation.tests import IntegrationTestCase


class TestConverter(IntegrationTestCase):

    def setUp(self):
        super(TestConverter, self).setUp()
        self.request = TestRequest()
        self.time = schema.Time()
        self.widget = TextWidget(self.request)

    def _convert(self, value):
        converter = FriendlyTimeDataConverter(self.time, self.widget)
        return converter.toFieldValue(value)

    def test_midnight(self):
        self.assertEqual(time(0, 0), self._convert('00:00'))
        self.assertEqual(time(0, 0), self._convert('0:00'))
        self.assertEqual(time(0, 0), self._convert('24:00'))

    def test_time_with_colon(self):
        self.assertEqual(time(9, 0), self._convert('09:00'))
        self.assertEqual(time(9, 0), self._convert('9:00'))

    def test_time_with_point(self):
        self.assertEqual(time(10, 13), self._convert('10.13'))
        self.assertEqual(time(1, 37), self._convert('1.37'))
        self.assertEqual(time(1, 37), self._convert('01.37'))

    def test_time_with_comma(self):
        self.assertEqual(time(10, 13), self._convert('10,13'))
        self.assertEqual(time(1, 37), self._convert('1,37'))
        self.assertEqual(time(1, 37), self._convert('01,37'))

    def test_time_with_semicolon(self):
        self.assertEqual(time(10, 13), self._convert('10;13'))
        self.assertEqual(time(1, 37), self._convert('1;37'))
        self.assertEqual(time(1, 37), self._convert('01;37'))

    def test_time_with_whitespaces(self):
        self.assertEqual(time(21, 59), self._convert(' 21  59 '))
        self.assertEqual(time(1, 33), self._convert(' 01 33 '))

    def test_time_with_characters(self):
        self.assertEqual(time(21, 59), self._convert('21h59'))
        self.assertEqual(time(7, 21), self._convert('7h21'))
        self.assertEqual(time(7, 21), self._convert('07h21'))
        self.assertEqual(time(7, 21), self._convert('gak7h21m'))

    def test_preceding_zeroes(self):
        self.assertEqual(time(23, 1), self._convert('23:001'))
        self.assertEqual(time(23, 1), self._convert('000023:01'))

    def test_out_of_bounds(self):
        self.assertRaises(FormatterValidationError, self._convert, '124:00')
        self.assertRaises(FormatterValidationError, self._convert, '23:61')

    def test_hour_out_of_range(self):
        self.assertRaises(FormatterValidationError, self._convert, '74:01')

    def test_minute_out_of_range(self):
        self.assertRaises(FormatterValidationError, self._convert, '15:61')

    def test_english_date_format(self):
        en = locales.getLocale('en', None, None)
        self.request._locale = en

        self.assertEqual(time(9, 0), self._convert('9:00 AM'))
        self.assertEqual(time(21, 0), self._convert('9:00 PM'))
