from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Allocation


class TestAllocation(IntegrationTestCase):

    def test_simple_add(self):
        # Test a simple add
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15)
        allocation.end = datetime(2011, 1, 1, 15, 59)
        allocation.group = uuid()

        Session.add(allocation)
        self.assertEqual(Session.query(Allocation).count(), 1)

        # Test failing add
        allocation = allocation(raster=15)

        Session.add(allocation)
        self.assertRaises(IntegrityError, Session.flush)