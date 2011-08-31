from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import DefinedTimeSpan


class TestDefinedTimeSpan(IntegrationTestCase):

    def test_simple_add(self):
        # Test a simple add
        span = DefinedTimeSpan(raster=15, resource=uuid())
        span.start = datetime(2011, 1, 1, 15)
        span.end = datetime(2011, 1, 1, 15, 59)

        Session.add(span)
        self.assertEqual(Session.query(DefinedTimeSpan).count(), 1)

        # Test failing add
        span = DefinedTimeSpan(raster=15)

        Session.add(span)
        self.assertRaises(IntegrityError, Session.flush)