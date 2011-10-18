from datetime import datetime
from uuid import uuid4 as uuid
from datetime import timedelta

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.db import Scheduler
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.error import AlreadyReservedError

class TestScheduler(IntegrationTestCase):

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

        # try to illegally move the slot
        movefn = lambda: sc.move_allocation(
                allocation.id, 
                datetime(2011, 1, 1, 15, 30),
                datetime(2011, 1, 1, 16),
                None
            )
        self.assertRaises(AffectedReservationError, movefn)

        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 2)

        # actually move the slot
        sc.move_allocation(
                allocation.id,
                datetime(2011, 1, 1, 15),
                datetime(2011, 1, 1, 15, 30),
                None
            )

        # there should be fewer slots now
        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 0)

        # remove the reservation
        sc.remove_reservation(reservation)

        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 2)

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

    def test_allocation_partition(self):
        sc = Scheduler(uuid())
        
        group, allocations = sc.allocate([
                (
                    datetime(2011, 1, 1, 8, 0), 
                    datetime(2011, 1, 1, 10, 0)
                )
            ])

        allocation = allocations[0]
        partitions = allocation.availability_partitions()
        self.assertEqual(len(partitions), 1)
        self.assertEqual(partitions[0][0], 100.0)
        self.assertEqual(partitions[0][1], False)

        start, end = datetime(2011, 1, 1, 8, 30), datetime(2011, 1, 1, 9, 00)
        sc.reserve([(start, end)])

        partitions = allocation.availability_partitions()
        self.assertEqual(len(partitions), 3)
        self.assertEqual(partitions[0][0], 25.00)
        self.assertEqual(partitions[0][1], False)
        self.assertEqual(partitions[1][0], 25.00)
        self.assertEqual(partitions[1][1], True)
        self.assertEqual(partitions[2][0], 50.00)
        self.assertEqual(partitions[2][1], False)

    def test_quotas(self):
        sc = Scheduler(uuid(), quota=10)
        
        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)

        # setup an allocation with ten spots
        group, allocations = sc.allocate([(start, end)], raster=15, quota=10)
        allocation = allocations[0]

        # which should give us ten allocations (-1 as the master is not counted)
        self.assertEqual(9, sc.allocation_mirrors_by_master(allocation).count())

        # the same reservation can now be made ten times
        for i in range(0, 10):
            sc.reserve([(start, end)])

        # the 11th time it'll fail
        self.assertRaises(AlreadyReservedError, sc.reserve, [(start, end)])

        sc = Scheduler(uuid(), quota=5)

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)

        # setup an allocation with five spots
        group, allocations = sc.allocate([(start, end)], raster=15, quota=5)
        allocation = allocations[0]

        self.assertEqual(4, sc.allocation_mirrors_by_master(allocation).count())

        # we can do ten reservations if every reservation only occupies half
        # of the allocation
        for i in range(0, 5):
            sc.reserve([(datetime(2011, 1, 1, 15, 0), datetime(2011, 1, 1, 15, 30))])
            sc.reserve([(datetime(2011, 1, 1, 15, 30), datetime(2011, 1, 1, 16, 0))])