from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import FlushError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Available
from seantis.reservation.models import ReservedSlot


class TestReservedSlot(IntegrationTestCase):

    def test_simple_add(self):

        # Add one slot together with a timespan
        available = Available(raster=15, resource=uuid())
        available.start = datetime(2011, 1, 1, 15)
        available.end = datetime(2011, 1, 1, 15, 59)
        available.group = uuid()

        reservation = uuid()

        slot = ReservedSlot(resource=available.resource)
        slot.start = available.start
        slot.end = available.end
        slot.available = available
        slot.reservation = reservation

        Session.add(available)
        Session.add(slot)

        self.assertEqual(available.reserved_slots.count(), 1)

        # Ensure that the same slot cannot be doubly used
        anotherslot = ReservedSlot(resource=available.resource)
        anotherslot.start = available.start
        anotherslot.end = available.end
        anotherslot.availalbe = available
        anotherslot.reservation = reservation

        Session.add(anotherslot)
        self.assertRaises(FlushError, Session.flush)