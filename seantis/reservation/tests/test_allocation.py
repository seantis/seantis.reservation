from datetime import datetime
from uuid import uuid1 as uuid

from sqlalchemy.exc import IntegrityError

from seantis.reservation import Session
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Allocation
from seantis.reservation.session import serialized


class TestAllocation(IntegrationTestCase):

    @serialized
    def test_simple_add(self):
        # Test a simple add
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15)
        allocation.end = datetime(2011, 1, 1, 15, 59)
        allocation.group = str(uuid())
        allocation.mirror_of = allocation.resource

        Session.add(allocation)

        self.assertEqual(Session.query(Allocation).count(), 1)

        # Test failing add
        allocation = Allocation(raster=15)

        Session.add(allocation)
        self.assertRaises(IntegrityError, Session.flush)

    def test_date_functions(self):
        allocation = Allocation(raster=60, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 12, 30)
        allocation.end = datetime(2011, 1, 1, 14, 00)

        self.assertEqual(allocation.start.hour, 12)
        self.assertEqual(allocation.start.minute, 0)

        self.assertEqual(allocation.end.hour, 13)
        self.assertEqual(allocation.end.minute, 59)

        start = datetime(2011, 1, 1, 11, 00)
        end = datetime(2011, 1, 1, 12, 05)

        self.assertTrue(allocation.overlaps(start, end))
        self.assertFalse(allocation.contains(start, end))

        start = datetime(2011, 1, 1, 13, 00)
        end = datetime(2011, 1, 1, 15, 00)

        self.assertTrue(allocation.overlaps(start, end))
        self.assertFalse(allocation.contains(start, end))

    def test_whole_day(self):
        allocation = Allocation(raster=15, resource=uuid())

        allocation.start = datetime(2013, 1, 1, 0, 0)
        allocation.end = datetime(2013, 1, 2, 0, 0)

        self.assertTrue(allocation.whole_day)

        allocation.start = datetime(2013, 1, 1, 0, 0)
        allocation.end = datetime(2013, 1, 1, 23, 59, 59, 999999)

        self.assertTrue(allocation.whole_day)

        allocation.start = datetime(2013, 1, 1, 0, 0)
        allocation.end = datetime(2013, 1, 2, 23, 59, 59, 999999)

        self.assertTrue(allocation.whole_day)

        allocation.start = datetime(2013, 1, 1, 0, 0)
        allocation.end = datetime(2013, 1, 2, 0, 0)

        self.assertTrue(allocation.whole_day)

        allocation.start = datetime(2013, 1, 1, 15, 0)
        allocation.end = datetime(2013, 1, 1, 0, 0)

        self.assertRaises(AssertionError, lambda: allocation.whole_day)
