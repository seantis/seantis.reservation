from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import DefinedTimeSpan
from seantis.reservation.models import ReservedTimeSlot


class TestReservedTimeSlot(IntegrationTestCase):

    def test_simple_add(self):

        # Add one slot together with a timespan
        span = DefinedTimeSpan(raster=15, resource=uuid())
        span.start = datetime(2011, 1, 1, 15)
        span.end = datetime(2011, 1, 1, 15, 59)

        slot = ReservedTimeSlot(resource=span.resource)
        slot.start = span.start
        slot.end = span.end
        slot.defined_timespan = span

        Session.add(span)
        Session.add(slot)

        self.assertEqual(span.reserved_slots.count(), 1)

        # Ensure that the same slot cannot be doubly used
        anotherslot = ReservedTimeSlot(resource=span.resource)
        anotherslot.start = span.start
        anotherslot.end = span.end
        anotherslot.defined_timespan = span

        Session.add(anotherslot)
        self.assertRaises(IntegrityError, Session.flush)