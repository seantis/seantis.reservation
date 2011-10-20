from datetime import datetime
from uuid import uuid4 as uuid

from sqlalchemy.exc import FlushError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation import Session


class TestReservedSlot(IntegrationTestCase):

    def test_simple_add(self):

        # Add one slot together with a timespan
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15)
        allocation.end = datetime(2011, 1, 1, 15, 59)
        allocation.group = str(uuid())

        reservation = uuid()

        slot = ReservedSlot(resource=allocation.resource)
        slot.start = allocation.start
        slot.end = allocation.end
        slot.allocation = allocation
        slot.reservation = reservation

        Session.add(allocation)
        Session.add(slot)

        self.assertEqual(allocation.reserved_slots.count(), 1)

        # Ensure that the same slot cannot be doubly used
        anotherslot = ReservedSlot(resource=allocation.resource)
        anotherslot.start = allocation.start
        anotherslot.end = allocation.end
        anotherslot.allocation = allocation
        anotherslot.reservation = reservation

        Session.add(anotherslot)
        self.assertRaises(FlushError, Session.flush)