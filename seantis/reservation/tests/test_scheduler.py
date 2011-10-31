from datetime import datetime
from uuid import uuid4 as new_uuid

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.db import Scheduler
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.error import AlreadyReservedError
from seantis.reservation import utils
from seantis.reservation.session import serialized

class TestScheduler(IntegrationTestCase):

    @serialized
    def test_reserve(self):
        sc = Scheduler(new_uuid())

        start = datetime(2011, 1, 1, 15)
        end = datetime(2011, 1, 1, 16)

        group, allocations = sc.allocate(
                (start, end), raster=15, partly_available=True
            )
        
        self.assertTrue(utils.is_uuid(group))
        self.assertEqual(1, len(allocations))
        
        allocation = allocations[0]

        # Add a second allocation in another scheduler, to ensure that
        # nothing bleeds over
        another = Scheduler(new_uuid())
        another.allocate((start, end))

        # 1 hour / 15 min = 4
        possible_dates = list(allocation.all_slots())
        self.assertEqual(len(possible_dates), 4)

        # reserve half of the slots
        time = (datetime(2011, 1, 1, 15), datetime(2011, 1, 1, 15, 30))
        reservation, slots = sc.reserve(time)

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
        sc1 = Scheduler(new_uuid())
        sc2 = Scheduler(new_uuid())

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        
        sc1.allocate((start, end), raster=15)
        sc2.allocate((start, end), raster=15)
        
        self.assertRaises(OverlappingAllocationError, 
                sc1.allocate, (start, end), raster=15
            )

    def test_allocation_partition(self):
        sc = Scheduler(new_uuid())
        
        group, allocations = sc.allocate(
                (
                    datetime(2011, 1, 1, 8, 0), 
                    datetime(2011, 1, 1, 10, 0)
                ),
                partly_available = True
            )

        allocation = allocations[0]
        partitions = allocation.availability_partitions()
        self.assertEqual(len(partitions), 1)
        self.assertEqual(partitions[0][0], 100.0)
        self.assertEqual(partitions[0][1], False)

        start, end = datetime(2011, 1, 1, 8, 30), datetime(2011, 1, 1, 9, 00)
        sc.reserve((start, end))

        partitions = allocation.availability_partitions()
        self.assertEqual(len(partitions), 3)
        self.assertEqual(partitions[0][0], 25.00)
        self.assertEqual(partitions[0][1], False)
        self.assertEqual(partitions[1][0], 25.00)
        self.assertEqual(partitions[1][1], True)
        self.assertEqual(partitions[2][0], 50.00)
        self.assertEqual(partitions[2][1], False)

    def test_partly(self):
        sc = Scheduler(new_uuid())

        allocations = sc.allocate(
                (
                    datetime(2011, 1, 1, 8, 0),
                    datetime(2011, 1, 1, 18, 0)
                ),
                partly_available = False
            )[1]

        self.assertEqual(1, len(allocations))
        allocation = allocations[0]

        self.assertEqual(1, len(list(allocation.all_slots())))
        self.assertEqual(1, len(list(allocation.free_slots())))

        slot = list(allocation.all_slots())[0]
        self.assertEqual(slot[0], allocation.start)
        self.assertEqual(slot[1], allocation.end)

        slot = list(allocation.free_slots())[0]
        self.assertEqual(slot[0], allocation.start)
        self.assertEqual(slot[1], allocation.end)

        sc.reserve((datetime(2011, 1, 1, 16, 0), datetime(2011, 1, 1, 18, 0)))
        self.assertRaises(AlreadyReservedError, sc.reserve, 
                (datetime(2011, 1, 1, 8, 0), datetime(2011, 1, 1, 9, 0))
            )

    @serialized
    def test_quotas(self):
        sc = Scheduler(new_uuid(), quota=10)
        
        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)

        # setup an allocation with ten spots
        group, allocations = sc.allocate((start, end), raster=15, quota=10)
        allocation = allocations[0]

        # which should give us ten allocations (-1 as the master is not counted)
        self.assertEqual(9, len(sc.allocation_mirrors_by_master(allocation)))

        # the same reservation can now be made ten times
        for i in range(0, 10):
            sc.reserve((start, end))

        # the 11th time it'll fail
        self.assertRaises(AlreadyReservedError, sc.reserve, [(start, end)])

        other = Scheduler(new_uuid(), quota=5)

        # setup an allocation with five spots
        group, allocations = other.allocate(
                [(start, end)], raster=15, quota=5, partly_available=True
            )
        allocation = allocations[0]

        self.assertEqual(4, len(other.allocation_mirrors_by_master(allocation)))

        # we can do ten reservations if every reservation only occupies half
        # of the allocation
        for i in range(0, 5):
            other.reserve((datetime(2011, 1, 1, 15, 0), datetime(2011, 1, 1, 15, 30)))
            other.reserve((datetime(2011, 1, 1, 15, 30), datetime(2011, 1, 1, 16, 0)))

        self.assertRaises(AlreadyReservedError, other.reserve,
                ((datetime(2011, 1, 1, 15, 30), datetime(2011, 1, 1, 16, 0)))
            )

        # test some queries
        allocations = sc.allocations_in_range(start, end)
        self.assertEqual(1, allocations.count())

        allocations = other.allocations_in_range(start, end)
        self.assertEqual(1, allocations.count())
        
        allocation = sc.allocation_by_date(start, end)
        sc.allocation_by_id(allocation.id)
        self.assertEqual(9, len(sc.allocation_mirrors_by_master(allocation)))

        allocation = other.allocation_by_date(start, end)    
        other.allocation_by_id(allocation.id)
        self.assertEqual(4, len(other.allocation_mirrors_by_master(allocation)))
    
    def test_fragmentation(self):
        sc = Scheduler(new_uuid(), quota=3)

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        daterange = (start, end)

        allocation = sc.allocate(daterange)[1][0]

        reservation, slots = sc.reserve(daterange)
        self.assertTrue([True for s in slots if s.resource == sc.uuid])
        
        slots = sc.reserve(daterange)[1]
        self.assertFalse([False for s in slots if s.resource == sc.uuid])

        sc.remove_reservation(reservation)

        slots = sc.reserve(daterange)[1]
        self.assertTrue([True for s in slots if s.resource == sc.uuid])

        self.assertRaises(
                AffectedReservationError, sc.remove_allocation, allocation.id
            )
    
    @serialized
    def test_imaginary_mirrors(self):
        sc = Scheduler(new_uuid(), quota=3)

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        daterange = (start, end)

        allocation = sc.allocate(daterange)[1][0]
        self.assertTrue(allocation.is_master)

        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 2)

        masters = len([m for m in mirrors if m.is_master])
        self.assertEqual(masters, 0)

        sc.reserve(daterange)
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 2)

        sc.reserve(daterange)
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 1)

        sc.reserve(daterange)
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 0)

    @serialized
    def test_quota_changes(self):
        sc = Scheduler(new_uuid(), quota=5)

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        daterange = (start, end)

        master = sc.allocate(daterange)[1][0]

        reservations = []
        for i in range(0, 5):
            reservations.append(sc.reserve(daterange)[0])

        mirrors = sc.allocation_mirrors_by_master(master)

        self.assertFalse(master.is_available())
        self.assertEqual(4, len([m for m in mirrors if not m.is_available()]))

        sc.remove_reservation(reservations[0])
        self.assertTrue(master.is_available())

        # by removing the reservation on the master and changing the quota
        # a reordering is triggered which will ensure that the master and the
        # mirrors are reserved without gaps (master, mirror 0, mirror 1 usw..)
        # so we should see an unavailable master after changing the quota
        sc.change_quota(master, 4)
        self.assertFalse(master.is_available())
        self.assertEqual(4, master.quota)

        mirrors = sc.allocation_mirrors_by_master(master)
        self.assertEqual(3, len([m for m in mirrors if not m.is_available()]))

        for reservation in reservations:
            sc.remove_reservation(reservation)

        self.assertTrue(master.is_available())
        mirrors = sc.allocation_mirrors_by_master(master)
        self.assertEqual(0, len([m for m in mirrors if not m.is_available()]))

        # let's do another round, adding 7 reservations and removing the three
        # in the middle, which should result in a reordering:
        # -> 1, 2, 3, 4, 5, 6, 7
        # -> 1, 2, -, -, 5, -, 7
        # => 1, 2, 3, 4, -, - ,-

        sc.change_quota(master, 7)
        
        sc.reserve(daterange)[0]
        r2 = sc.reserve(daterange)[0]
        r3 = sc.reserve(daterange)[0]
        r4 = sc.reserve(daterange)[0]
        r5 = sc.reserve(daterange)[0]
        r6 = sc.reserve(daterange)[0]
        r7 = sc.reserve(daterange)[0]

        a2 = sc.allocations_by_reservation(r2).one().id
        a3 = sc.allocations_by_reservation(r3).one().id
        a4 = sc.allocations_by_reservation(r4).one().id
        a5 = sc.allocations_by_reservation(r5).one().id
        a7 = sc.allocations_by_reservation(r7).one().id

        sc.remove_reservation(r3)
        sc.remove_reservation(r4)
        sc.remove_reservation(r6)

        sc.change_quota(master, 4)

        a2_ = sc.allocations_by_reservation(r2).one().id
        a5_ = sc.allocations_by_reservation(r5).one().id
        a7_ = sc.allocations_by_reservation(r7).one().id

        self.assertTrue(a2_ == a2)

        self.assertTrue(a5_ == a3)
        self.assertTrue(a5_ != a5)

        self.assertTrue(a7_ == a4)
        self.assertTrue(a7_ != a7)
