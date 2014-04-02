import transaction
import mock

from collections import namedtuple
from threading import Thread
from uuid import uuid1 as uuid
from datetime import datetime
from seantis.reservation.tests import IntegrationTestCase

from seantis.reservation.session import (
    getUtility,
    ISessionUtility,
    serialized
)

from seantis.reservation import Session
from seantis.reservation.models import Allocation
from seantis.reservation.error import (
    DirtyReadOnlySession,
    ModifiedReadOnlySession,
    TransactionRollbackError
)


class SessionIds(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.serial_id = None
        self.readonly_id = None

    def run(self):
        util = getUtility(ISessionUtility)

        self.serial_id = id(util.sessionstore.serial)
        self.readonly_id = id(util.sessionstore.readonly)


class ExceptionThread(Thread):
    def __init__(self, call):
        Thread.__init__(self)
        self.call = call
        self.exception = None

    def run(self):
        try:
            self.call()
            import time
            time.sleep(1)
            transaction.commit()
        except Exception, e:
            self.exception = e


def add_something(resource=None):
    resource = resource or uuid()
    allocation = Allocation(raster=15, resource=resource, mirror_of=resource)
    allocation.start = datetime(2011, 1, 1, 15)
    allocation.end = datetime(2011, 1, 1, 15, 59)
    allocation.group = uuid()

    Session.add(allocation)


class TestSession(IntegrationTestCase):

    @mock.patch('seantis.reservation.utils.get_config')
    def test_dsnconfig(self, get_config):
        util = getUtility(ISessionUtility)
        util._default_dsn = 'test://default'

        MockSite = namedtuple('MockSite', ['id'])

        get_config.return_value = None
        self.assertEqual(util.get_dsn(MockSite('test')), 'test://default')

        get_config.return_value = 'test://specific'
        self.assertEqual(util.get_dsn(MockSite('test2')), 'test://specific')

        get_config.return_value = 'test://{*}'
        self.assertEqual(util.get_dsn(MockSite('test3')), 'test://test3')

        util._default_dsn = 'test://{*}'
        get_config.return_value = None
        self.assertEqual(util.get_dsn(MockSite('test4')), 'test://test4')

    def test_sessionstore(self):

        t1 = SessionIds()
        t2 = SessionIds()

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.assertFalse(t1.serial_id is None)
        self.assertFalse(t2.serial_id is None)
        self.assertFalse(t1.serial_id == t2.serial_id)
        self.assertFalse(t1.readonly_id == t2.readonly_id)

    def test_readonly_protection(self):
        add_something()

        self.assertRaises(ModifiedReadOnlySession)

    def test_dirty_protection(self):

        Session.flush()  # should not throw an exception

        serialized(lambda: None)()

        Session.flush()  # nothing happened, no exception

        serialized(add_something)()

        self.assertRaises(DirtyReadOnlySession, lambda: Session.flush)

    def test_collission(self):

        # for this test to work we need something commited (delete it later)
        def commit():
            add_something()
            transaction.commit()

        serialized(commit)()

        try:
            def change_allocation():
                allocation = Session.query(Allocation).one()
                allocation.group = uuid()

            t1 = ExceptionThread(serialized(change_allocation))
            t2 = ExceptionThread(serialized(change_allocation))

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            exceptions = (t1.exception, t2.exception)

            is_rollback = lambda ex: \
                ex and isinstance(ex.orig, TransactionRollbackError)
            is_nothing = lambda ex: not is_rollback(ex)

            rollbacks = filter(is_rollback, exceptions)
            updates = filter(is_nothing, exceptions)

            self.assertEqual(1, len(rollbacks))
            self.assertEqual(1, len(updates))

        finally:
            def drop():
                Session.query(Allocation).delete()
                transaction.commit()

            serialized(drop)()

    def test_non_collision(self):
        # same as above, but this time the second session is read only and
        # should therefore not have an impact on existing code

        def commit():
            add_something()
            transaction.commit()

        serialized(commit)()

        try:
            def change_allocation():
                allocation = Session.query(Allocation).one()
                allocation.group = uuid()

            def read_allocation():
                allocation = Session.query(Allocation).one()
                allocation.resource

            t1 = ExceptionThread(serialized(change_allocation))
            t2 = ExceptionThread(read_allocation)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            exceptions = (t1.exception, t2.exception)

            is_rollback = lambda ex: \
                ex and isinstance(ex.orig, TransactionRollbackError)
            rollbacks = filter(is_rollback, exceptions)

            self.assertEqual(0, len(rollbacks))

        finally:
            def drop():
                Session.query(Allocation).delete()
                transaction.commit()

            serialized(drop)()
