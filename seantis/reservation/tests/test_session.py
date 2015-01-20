import mock

from collections import namedtuple
from uuid import uuid1 as uuid
from datetime import datetime
from seantis.reservation.tests import IntegrationTestCase

from seantis.reservation.session import (
    getUtility,
    ILibresUtility
)

from seantis.reservation import Session
from libres.db.models import Allocation


def add_something(resource=None):
    resource = resource or uuid()
    allocation = Allocation(
        raster=15, resource=resource, mirror_of=resource)
    allocation.start = datetime(2011, 1, 1, 15)
    allocation.end = datetime(2011, 1, 1, 15, 59)
    allocation.group = uuid()

    Session.add(allocation)


class TestSession(IntegrationTestCase):

    @mock.patch('seantis.reservation.utils.get_config')
    def test_dsnconfig(self, get_config):
        util = getUtility(ILibresUtility)
        util._default_dsn = 'test://default'

        MockSite = namedtuple('MockSite', ['id'])

        get_config.return_value = None
        self.assertEqual(util.get_dsn(MockSite('test')), 'test://default')

        get_config.return_value = 'test://specific'
        self.assertEqual(util.get_dsn(MockSite('test2')), 'test://specific')

        get_config.return_value = 'test://{*}'
        self.assertEqual(util.get_dsn(MockSite('test3')), 'test://test3')

        util._default_dsn = 'test://{*}'
        get_config.return_value = None
        self.assertEqual(util.get_dsn(MockSite('test4')), 'test://test4')
