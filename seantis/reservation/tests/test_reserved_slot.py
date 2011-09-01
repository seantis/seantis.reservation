from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import FlushError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import DefinedTimeSpan
from seantis.reservation.models import ReservedSlot


class TestReservedSlot(IntegrationTestCase):

    def test_simple_add(self):

        # Add one slot together with a timespan
        span = DefinedTimeSpan(raster=15, resource=uuid())
        span.start = datetime(2011, 1, 1, 15)
        span.end = datetime(2011, 1, 1, 15, 59)

        reservation = uuid()

        slot = ReservedSlot(resource=span.resource)
        slot.start = span.start
        slot.end = span.end
        slot.defined_timespan = span
        slot.reservation = reservation

        Session.add(span)
        Session.add(slot)

        self.assertEqual(span.reserved_slots.count(), 1)

        # Ensure that the same slot cannot be doubly used
        anotherslot = ReservedSlot(resource=span.resource)
        anotherslot.start = span.start
        anotherslot.end = span.end
        anotherslot.defined_timespan = span
        anotherslot.reservation = reservation

        Session.add(anotherslot)
        self.assertRaises(FlushError, Session.flush)