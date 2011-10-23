from threading import Thread
from uuid import uuid4 as uuid
from datetime import datetime
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.session import getUtility, ISessionUtility, serialized_call
from seantis.reservation import Session
from seantis.reservation.models import Allocation
from seantis.reservation.error import DirtyReadOnlySession, ModifiedReadOnlySession

class SessionIds(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.serial_id = None
        self.readonly_id = None
    
    def run(self):
        util = getUtility(ISessionUtility)
        self.serial_id = id(util.threadstore.serial_session)
        self.readonly_id = id(util.threadstore.main_session)

def add_something():
    allocation = Allocation(raster=15, resource=uuid())
    allocation.start = datetime(2011, 1, 1, 15)
    allocation.end = datetime(2011, 1, 1, 15, 59)
    allocation.group = str(uuid())

    Session.add(allocation)

class TestScheduler(IntegrationTestCase):

    def test_threadstore(self):
        t1 = SessionIds()
        t2 = SessionIds()

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.assertFalse(t1.serial_id == None)
        self.assertFalse(t2.serial_id == None)
        self.assertFalse(t1.serial_id == t2.serial_id)
        self.assertFalse(t1.readonly_id == t2.readonly_id)

    def test_readonly_protection(self):
        add_something()

        self.assertRaises(ModifiedReadOnlySession)

    def test_dirty_protection(self):

        Session.flush() # should not throw an exception

        serialized_call(lambda: None)()

        Session.flush() # nothing happened, no exception

        serialized_call(add_something)()

        self.assertRaises(DirtyReadOnlySession, lambda: Session.flush)