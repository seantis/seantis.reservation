import unittest2 as unittest
from seantis.reservation.testing import SEANTIS_RESERVATION_INTEGRATION_TESTING
from seantis.reservation.testing import SEANTIS_RESERVATION_FUNCTIONAL_TESTING

class TestCase(unittest.TestCase):
    pass

class IntegrationTestCase(TestCase):

    layer = SEANTIS_RESERVATION_INTEGRATION_TESTING

class FunctionalTestCase(TestCase):

    layer = SEANTIS_RESERVATION_FUNCTIONAL_TESTING