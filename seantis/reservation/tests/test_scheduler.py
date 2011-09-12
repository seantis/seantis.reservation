from datetime import datetime
from uuid import uuid4 as uuid
from datetime import timedelta

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.scheduler import Scheduler
from seantis.reservation.error import OverlappingAllocationError

class TestScheduler(IntegrationTestCase):

    def test_allocations_in_range(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        sc.allocate(((start, end),), raster=15)

        hour = timedelta(minutes=60)
        
        self.assertTrue(sc.any_allocations_in_range(start, end))
        self.assertTrue(sc.any_allocations_in_range(start - hour, end + hour))
        self.assertFalse(sc.any_allocations_in_range(start + hour, end - hour))

    def test_reserve(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15)
        end = datetime(2011, 1, 1, 16)
        group, allocations = sc.allocate(((start, end),), raster=15)
        allocation = allocations[0]

        possible_dates = list(allocation.all_slots())

        # 1 hour / 15 min = 4
        self.assertEqual(len(possible_dates), 4)

        # reserve half of the slots
        time = (datetime(2011, 1, 1, 15), datetime(2011, 1, 1, 15, 30))
        reservation, slots = sc.reserve((time,))

        self.assertEqual(len(slots), 2)

        # check the remaining slots
        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining, possible_dates[2:])

        reserved_slots = list(sc.reserved_slots(reservation))
        self.assertEqual(slots, reserved_slots)

        # remove the reservation
        sc.remove_reservation(reservation)

        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 4)

    def test_allocation_overlap(self):
        sc1 = Scheduler(uuid())
        sc2 = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        
        sc1.allocate(((start, end),), raster=15)
        sc2.allocate(((start, end),), raster=15)
        
        self.assertRaises(OverlappingAllocationError, 
                sc1.allocate, ((start, end),), raster=15
            )