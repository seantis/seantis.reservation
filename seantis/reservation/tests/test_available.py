from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Available


class TestAvailable(IntegrationTestCase):

    def test_simple_add(self):
        # Test a simple add
        available = Available(raster=15, resource=uuid())
        available.start = datetime(2011, 1, 1, 15)
        available.end = datetime(2011, 1, 1, 15, 59)
        available.group = uuid()

        Session.add(available)
        self.assertEqual(Session.query(Available).count(), 1)

        # Test failing add
        available = Available(raster=15)

        Session.add(available)
        self.assertRaises(IntegrityError, Session.flush)