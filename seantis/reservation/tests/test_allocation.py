from datetime import datetime
from seantis.reservation import Session
from seantis.reservation.models import Allocation
from seantis.reservation.models.blocked_period import BlockedPeriod
from seantis.reservation.session import serialized
from seantis.reservation.tests import IntegrationTestCase
from sqlalchemy.exc import IntegrityError
from uuid import uuid1 as uuid


class TestAllocationIsBlocked(IntegrationTestCase):
    """Test that is_blocked works as expected for all ranges

          |-------------------|          *compare to this one*
    blocked:
              |---------|                contained within
          |----------|                   contained within, equal start
                  |-----------|          contained within, equal end
          |-------------------|          contained within, equal start+end
    |------------|                       not fully contained, overlaps start
                  |---------------|      not fully contained, overlaps end
    |-------------------------|          overlaps start, bigger
    |------------------------------|     overlaps entire period
    not blocked:
     |---|                                ends before
                                 |---|    starts after

    see: http://stackoverflow.com/questions/143552/comparing-date-ranges
    """

    def setUp(self):
        super(TestAllocationIsBlocked, self).setUp()
        self.allocation = self._create_allocation()

    def _create_allocation(self):
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15, 00)
        allocation.end = datetime(2011, 1, 1, 16, 00)
        allocation.group = str(uuid())
        allocation.mirror_of = allocation.resource
        Session.add(allocation)
        return allocation

    def _create_blocked_period(self, resource, start, end):
        blocked = BlockedPeriod(resource=resource,
                                token=uuid(),
                                start=start,
                                end=end)
        Session.add(blocked)
        return blocked

    def assertAllocationIsBlocked(self, start, end):
        self._create_blocked_period(self.allocation.resource,
                                    start,
                                    end)
        self.assertTrue(self.allocation.is_blocked())

    def assertAllocationIsNotBlocked(self, start, end):
        self._create_blocked_period(self.allocation.resource,
                                    start,
                                    end)
        self.assertFalse(self.allocation.is_blocked())

    @serialized
    def test_contained_within(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 30),
                                       datetime(2011, 1, 1, 15, 45))

    @serialized
    def test_contained_within_equal_start(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 00),
                                       datetime(2011, 1, 1, 15, 45))

    @serialized
    def test_contained_within_equal_end(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 15),
                                       datetime(2011, 1, 1, 16, 00))

    @serialized
    def test_contained_within_equal_start_and_end(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 00),
                                       datetime(2011, 1, 1, 16, 00))

    @serialized
    def test_not_fully_contained_overlaps_start(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 14, 00),
                                       datetime(2011, 1, 1, 15, 30))

    @serialized
    def test_not_fully_contained_overlaps_end(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 30),
                                       datetime(2011, 1, 1, 16, 30))

    @serialized
    def test_overlaps_start_bigger(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 14, 30),
                                       datetime(2011, 1, 1, 16, 00))

    @serialized
    def test_overlaps_end_bigger(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 15, 00),
                                       datetime(2011, 1, 1, 16, 30))

    @serialized
    def test_overlaps_entire_period(self):
        self.assertAllocationIsBlocked(datetime(2011, 1, 1, 14, 30),
                                       datetime(2011, 1, 1, 16, 30))

    @serialized
    def test_ends_before(self):
        self.assertAllocationIsNotBlocked(datetime(2011, 1, 1, 14, 30),
                                          datetime(2011, 1, 1, 14, 45))

    @serialized
    def test_starts_after(self):
        self.assertAllocationIsNotBlocked(datetime(2011, 1, 1, 16, 15),
                                          datetime(2011, 1, 1, 16, 45))


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
