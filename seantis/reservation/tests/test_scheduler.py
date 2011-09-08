from datetime import datetime
from uuid import uuid4 as uuid
from datetime import timedelta

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.scheduler import Scheduler
from seantis.reservation.error import OverlappingAvailable

class TestScheduler(IntegrationTestCase):

    def test_available_in_range(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        sc.make_available(((start, end),), raster=15)

        hour = timedelta(minutes=60)
        
        self.assertTrue(sc.any_available_in_range(start, end))
        self.assertTrue(sc.any_available_in_range(start - hour, end + hour))
        self.assertFalse(sc.any_available_in_range(start + hour, end - hour))

    def test_reserve(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15)
        end = datetime(2011, 1, 1, 16)
        group, availables = sc.make_available(((start, end),), raster=15)
        available = availables[0]

        possible_dates = list(available.all_slots())

        # 1 hour / 15 min = 4
        self.assertEqual(len(possible_dates), 4)

        # reserve half of the slots
        time = (datetime(2011, 1, 1, 15), datetime(2011, 1, 1, 15, 30))
        reservation, slots = sc.reserve((time,))

        self.assertEqual(len(slots), 2)

        # check the remaining slots
        remaining = available.free_slots()
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining, possible_dates[2:])

        reserved_slots = list(sc.reserved_slots(reservation))
        self.assertEqual(slots, reserved_slots)

        # remove the reservation
        sc.remove_reservation(reservation)

        remaining = available.free_slots()
        self.assertEqual(len(remaining), 4)

    def test_available_overlap(self):
        sc1 = Scheduler(uuid())
        sc2 = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        
        sc1.make_available(((start, end),), raster=15)
        sc2.make_available(((start, end),), raster=15)
        
        self.assertRaises(OverlappingAvailable, 
                sc1.make_available, ((start, end),), raster=15
            )