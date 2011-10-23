import unittest2 as unittest

from seantis.reservation import setuphandlers
from seantis.reservation import Session
from seantis.reservation.session import getUtility, ISessionUtility

from seantis.reservation.testing import SQL_INTEGRATION_TESTING
from seantis.reservation.testing import SQL_FUNCTIONAL_TESTING

class TestCase(unittest.TestCase):

    def setUp(self):
        #getUtility(ISessionUtility).use_serial_session()
        setuphandlers.dbsetup(None)

    def tearDown(self):
        util = getUtility(ISessionUtility)
        util.threadstore.main_session.rollback()
        util.threadstore.serial_session.rollback()
        
class IntegrationTestCase(TestCase):
    layer = SQL_INTEGRATION_TESTING

class FunctionalTestCase(TestCase):
    layer = SQL_FUNCTIONAL_TESTING