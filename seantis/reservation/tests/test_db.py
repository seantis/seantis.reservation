from datetime import datetime, timedelta
from uuid import uuid4 as new_uuid

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.db import Scheduler
from seantis.reservation.error import OverlappingAllocationError
from seantis.reservation.error import AffectedReservationError
from seantis.reservation.error import AlreadyReservedError
from seantis.reservation.error import ReservationTooLong
from seantis.reservation.error import NotReservableError
from seantis.reservation.error import FullWaitingList
from seantis.reservation import utils
from seantis.reservation.session import serialized

class TestScheduler(IntegrationTestCase):

    @serialized
    def test_reserve(self):
        sc = Scheduler(new_uuid())

        start = datetime(2011, 1, 1, 15)
        end = datetime(2011, 1, 1, 16)
        
        allocations = sc.allocate(
                (start, end), raster=15, partly_available=True
            )
        
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
        token = sc.reserve(time)
        slots = sc.confirm_reservation(token)

        self.assertEqual(len(slots), 2)

        # check the remaining slots
        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining, possible_dates[2:])

        reserved_slots = sc.reserved_slots_by_reservation(token).all()
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
        sc.remove_reservation(token)

        remaining = allocation.free_slots()
        self.assertEqual(len(remaining), 2)

    @serialized
    def test_waitlist(self):
        sc = Scheduler(new_uuid())

        start = datetime(2012, 2, 29, 15, 0)
        end = datetime(2012, 2, 29, 19, 0)
        dates = (start, end)

        # let's create an allocation with three spots in the waiting list
        allocation = sc.allocate(dates, waitinglist_spots=1)[0]
        self.assertEqual(allocation.open_waitinglist_spots(), 1)

        # first reservation should work
        confirmed_token = sc.reserve(dates)
        self.assertTrue(allocation.is_available(start, end))
        
        # which results in a full waiting list (as the reservation is pending)
        self.assertEqual(allocation.open_waitinglist_spots(), 0)

        # as well as it's confirmation
        sc.confirm_reservation(confirmed_token)
        self.assertFalse(allocation.is_available(start, end))

        # this leaves one waiting list spot
        self.assertEqual(allocation.open_waitinglist_spots(), 1)

        # at this point we can only reserve, not confirm
        waiting_token = sc.reserve(dates)
        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, waiting_token)

        # the waiting list should be full now
        self.assertEqual(allocation.open_waitinglist_spots(), 0)

        # we may now get rid of the existing confirmed reservation
        sc.remove_reservation(confirmed_token)
        self.assertEqual(allocation.open_waitinglist_spots(), 0)

        # which should allow us to confirm the reservation in the waiting list
        sc.confirm_reservation(waiting_token)
        self.assertEqual(allocation.open_waitinglist_spots(), 1)

    @serialized
    def test_waitlist_group(self):
        from dateutil.rrule import rrule, DAILY, MO

        sc = Scheduler(new_uuid())
        days = list(rrule(DAILY, count=5, byweekday=(MO,), dtstart=datetime(2012,1,1)))
        dates = []
        for d in days:
            dates.append(
                (
                    datetime(d.year, d.month, d.day, 15, 0), 
                    datetime(d.year, d.month, d.day, 16, 0)
                )
            )
        
        allocations = sc.allocate(dates, grouped=True, waitinglist_spots=2)
        self.assertEqual(len(allocations), 5)

        group = allocations[0].group

        # reserving groups is no different than single allocations
        maintoken = sc.reserve(group=group)
        sc.confirm_reservation(maintoken)

        token = sc.reserve(group=group)
        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, token)

        token = sc.reserve(group=group)
        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, token)

        self.assertRaises(FullWaitingList, sc.reserve, None, group)

        # the only thing changing is the fact that removing part of the reservation
        # does not delete the reservation record
        sc.remove_reservation(maintoken, allocations[0].start, allocations[0].end)

        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, token)

        sc.remove_reservation(maintoken)

        sc.confirm_reservation(token)        

    @serialized
    def test_no_waitlist(self):
        sc = Scheduler(new_uuid())

        start = datetime(2012, 4, 6, 22, 0)
        end = datetime(2012, 4, 6, 23, 0)
        dates = (start, end)

        allocation = sc.allocate(dates, waitinglist_spots=0)[0]
        self.assertEqual(allocation.open_waitinglist_spots(), 0)
        self.assertEqual(allocation.pending_reservations(), 0)

        # the first reservation kinda gets us in a waiting list, though
        # this time there can be only one spot in the list as long as there's
        # no reservation

        token = sc.reserve(dates) 
        sc.confirm_reservation(token)

        # it is now that we should have a problem reserving
        self.assertRaises(AlreadyReservedError, sc.reserve, dates)

        # until we delete the existing reservation
        sc.remove_reservation(token)
        sc.reserve(dates)

    @serialized
    def test_quota_waitlist(self):
        sc = Scheduler(new_uuid())

        start = datetime(2012, 3, 4, 2, 0)
        end = datetime(2012, 3, 4, 3, 0)
        dates = (start, end)

        # in this example the waiting list will kick in only after
        # the quota has been filled

        allocation = sc.allocate(dates, quota=2, waitinglist_spots=2)[0]
        self.assertEqual(allocation.open_waitinglist_spots(), 2)

        t1 = sc.reserve(dates)
        t2 = sc.reserve(dates)
        
        self.assertEqual(allocation.open_waitinglist_spots(), 0)

        sc.confirm_reservation(t1)
        sc.confirm_reservation(t2)

        self.assertEqual(allocation.open_waitinglist_spots(), 2)

        t3 = sc.reserve(dates)
        t4 = sc.reserve(dates)

        self.assertEqual(allocation.open_waitinglist_spots(), 0)

        self.assertRaises(FullWaitingList, sc.reserve, dates)
        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, t3)
        self.assertRaises(AlreadyReservedError, sc.confirm_reservation, t4)

    def test_userlimits(self):
        # ensure that no user can make a reservation for more than 24 hours at 
        # the time. the user acutally can't do that anyway, since we do not offer
        # start / end dates, but a day and two times. But if this changes in the 
        # future it should throw en error first, because it would mean that we
        # have to look at how to stop the user from reserving one year with a single
        # form

        start = datetime(2011, 1, 1, 15, 0)
        end = start + timedelta(days=1)

        sc = Scheduler(new_uuid())

        self.assertRaises(ReservationTooLong, sc.reserve, (start, end))

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
        
        allocations = sc.allocate(
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

        token = sc.reserve((start, end))
        sc.confirm_reservation(token)

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
            )

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

        token = sc.reserve((datetime(2011, 1, 1, 16, 0), datetime(2011, 1, 1, 18, 0)))
        sc.confirm_reservation(token)
        self.assertRaises(AlreadyReservedError, sc.reserve, 
                (datetime(2011, 1, 1, 8, 0), datetime(2011, 1, 1, 9, 0))
            )

    @serialized
    def test_quotas(self):
        sc = Scheduler(new_uuid(), quota=10)
        
        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)

        # setup an allocation with ten spots
        allocations = sc.allocate((start, end), raster=15, quota=10)
        allocation = allocations[0]

        # which should give us ten allocations (-1 as the master is not counted)
        self.assertEqual(9, len(sc.allocation_mirrors_by_master(allocation)))

        # the same reservation can now be made ten times
        for i in range(0, 10):
            sc.confirm_reservation(sc.reserve((start, end)))

        # the 11th time it'll fail
        self.assertRaises(AlreadyReservedError, sc.reserve, [(start, end)])

        other = Scheduler(new_uuid(), quota=5)

        # setup an allocation with five spots
        allocations = other.allocate(
                [(start, end)], raster=15, quota=5, partly_available=True
            )
        allocation = allocations[0]

        self.assertEqual(4, len(other.allocation_mirrors_by_master(allocation)))

        # we can do ten reservations if every reservation only occupies half
        # of the allocation
        for i in range(0, 5):
            other.confirm_reservation(
                other.reserve((datetime(2011, 1, 1, 15, 0), datetime(2011, 1, 1, 15, 30)))
            )
            other.confirm_reservation(
                other.reserve((datetime(2011, 1, 1, 15, 30), datetime(2011, 1, 1, 16, 0)))
            )

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

        allocation = sc.allocate(daterange)[0]

        reservation = sc.reserve(daterange)
        slots = sc.confirm_reservation(reservation)
        self.assertTrue([True for s in slots if s.resource == sc.uuid])
        
        slots = sc.confirm_reservation(sc.reserve(daterange))
        self.assertFalse([False for s in slots if s.resource == sc.uuid])

        sc.remove_reservation(reservation)

        slots = sc.confirm_reservation(sc.reserve(daterange))
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

        allocation = sc.allocate(daterange)[0]
        self.assertTrue(allocation.is_master)

        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 2)
        self.assertEqual(len(allocation.siblings()),3)

        masters = len([m for m in mirrors if m.is_master])
        self.assertEqual(masters, 0)
        self.assertEqual(len([s for s in allocation.siblings(imaginary=False)]),1)

        sc.confirm_reservation(sc.reserve(daterange))
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 2)

        sc.confirm_reservation(sc.reserve(daterange))
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 1)

        sc.confirm_reservation(sc.reserve(daterange))
        mirrors = sc.allocation_mirrors_by_master(allocation)
        imaginary = len([m for m in mirrors if m.is_transient])
        self.assertEqual(imaginary, 0)
        self.assertEqual(len(mirrors) + 1, len(allocation.siblings()))

    @serialized
    def test_quota_changes(self):
        sc = Scheduler(new_uuid(), quota=5)

        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)
        daterange = (start, end)

        master = sc.allocate(daterange)[0]

        reservations = []
        for i in range(0, 5):
            reservations.append(sc.reserve(daterange))

        for r in reservations:
            sc.confirm_reservation(r)

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

        # this is a good time to check if the siblings function from the allocation
        # acts the same on each mirror and master
        siblings = master.siblings()
        for s in siblings:
            self.assertEqual(s.siblings(), siblings)

        # let's do another round, adding 7 reservations and removing the three
        # in the middle, which should result in a reordering:
        # -> 1, 2, 3, 4, 5, 6, 7
        # -> 1, 2, -, -, 5, -, 7
        # => 1, 2, 3, 4, -, - ,-

        sc.change_quota(master, 7)
        
        sc.reserve(daterange)
        r2 = sc.reserve(daterange)
        r3 = sc.reserve(daterange)
        r4 = sc.reserve(daterange)
        r5 = sc.reserve(daterange)
        r6 = sc.reserve(daterange)
        r7 = sc.reserve(daterange)

        for r in [r2, r3, r4, r5, r6, r7]:
            sc.confirm_reservation(r)

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

    @serialized
    def test_availability(self):
        start = datetime(2011, 1, 1, 15, 0)
        end = datetime(2011, 1, 1, 16, 0)

        sc = Scheduler(new_uuid())
        a = sc.allocate((start, end), raster=15, partly_available=True)[0]

        sc.confirm_reservation(
            sc.reserve((datetime(2011, 1, 1, 15, 0), datetime(2011, 1, 1, 15, 15)))
        )

        self.assertEqual(a.availability, 75.0)
        self.assertEqual(a.availability, sc.availability())
        
        sc.confirm_reservation(
            sc.reserve((datetime(2011, 1, 1, 15, 45), datetime(2011, 1, 1, 16, 0)))
        )
        self.assertEqual(a.availability, 50.0)
        self.assertEqual(a.availability, sc.availability())

        sc.confirm_reservation(
            sc.reserve((datetime(2011, 1, 1, 15, 15), datetime(2011, 1, 1, 15, 30)))
        )
        self.assertEqual(a.availability, 25.0)
        self.assertEqual(a.availability, sc.availability())

        sc.confirm_reservation(
            sc.reserve((datetime(2011, 1, 1, 15, 30), datetime(2011, 1, 1, 15, 45)))
        )
        self.assertEqual(a.availability, 0.0)
        self.assertEqual(a.availability, sc.availability())

        sc = Scheduler(new_uuid())
        
        a = sc.allocate((start, end), quota=4)[0]
        
        self.assertEqual(a.availability, 100.0) # master only!

        sc.confirm_reservation(
            sc.reserve((start, end))
        )

        self.assertEqual(75.0, sc.availability())

        self.assertEqual(a.availability, 0.0) # master only!

        sc.confirm_reservation(
            sc.reserve((start, end))
        )
        self.assertEqual(50.0, sc.availability())        

        sc.confirm_reservation(
            sc.reserve((start, end))
        )
        self.assertEqual(25.0, sc.availability())

        sc.confirm_reservation(
            sc.reserve((start, end))
        )
        self.assertEqual(0.0, sc.availability())