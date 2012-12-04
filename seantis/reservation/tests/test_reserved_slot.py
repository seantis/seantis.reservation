from datetime import datetime
from uuid import uuid1 as uuid


from seantis.reservation.error import IntegrityError
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Allocation
from seantis.reservation.models import ReservedSlot
from seantis.reservation import Session
from seantis.reservation.session import serialized


class TestReservedSlot(IntegrationTestCase):

    @serialized
    def test_simple_add(self):

        # Add one slot together with a timespan
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15)
        allocation.end = datetime(2011, 1, 1, 15, 59)
        allocation.group = uuid()

        reservation = uuid()

        slot = ReservedSlot(resource=allocation.resource)
        slot.start = allocation.start
        slot.end = allocation.end
        slot.allocation = allocation
        slot.reservation = reservation
        allocation.reserved_slots.append(slot)

        # Ensure that the same slot cannot be doubly used
        anotherslot = ReservedSlot(resource=allocation.resource)
        anotherslot.start = allocation.start
        anotherslot.end = allocation.end
        anotherslot.allocation = allocation
        anotherslot.reservation = reservation

        Session.add(anotherslot)
        self.assertRaises(IntegrityError, Session.flush)
