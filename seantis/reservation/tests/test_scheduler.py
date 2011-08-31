from datetime import datetime
from uuid import uuid4 as uuid
from datetime import timedelta

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.scheduler import Scheduler

class TestScheduler(IntegrationTestCase):

    def test_defined_in_range(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        sc.define(((start, end),), raster=15)

        hour = timedelta(minutes=60)
        
        self.assertTrue(sc.any_defined_in_range(start, end))
        self.assertTrue(sc.any_defined_in_range(start - hour, end + hour))
        self.assertFalse(sc.any_defined_in_range(start + hour, end - hour))

    def test_reserve(self):
        sc = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15)
        end = datetime(2011, 1, 1, 16)
        span = sc.define(((start, end),), raster=15)[0]

        possible_dates = list(span.possible_dates())

        # 1 hour / 15 min = 4
        self.assertEqual(len(possible_dates), 4)

        # reserve half of the slots
        time = (datetime(2011, 1, 1, 15), datetime(2011, 1, 1, 15, 30))
        slots = sc.reserve((time,))

        self.assertEqual(len(slots), 2)

        # check the remaining slots
        remaining = span.open_dates()
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining, possible_dates[2:])

    def test_define_overlap(self):
        sc1 = Scheduler(uuid())
        sc2 = Scheduler(uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        
        self.assertTrue(sc1.define(((start, end),), raster=15) != None)
        self.assertTrue(sc2.define(((start, end),), raster=15) != None)
        self.assertTrue(sc1.define(((start, end),), raster=15) == None)