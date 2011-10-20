import unittest2 as unittest

from seantis.reservation import Session

from seantis.reservation.testing import SEANTIS_RESERVATION_INTEGRATION_TESTING
from seantis.reservation.testing import SEANTIS_RESERVATION_FUNCTIONAL_TESTING

class TestCase(unittest.TestCase):
    def tearDown(self):
        Session.rollback()

class IntegrationTestCase(TestCase):

    layer = SEANTIS_RESERVATION_INTEGRATION_TESTING

class FunctionalTestCase(TestCase):

    layer = SEANTIS_RESERVATION_FUNCTIONAL_TESTING