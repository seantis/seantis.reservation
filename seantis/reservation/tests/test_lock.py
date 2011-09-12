from threading import Lock
from threading import Thread

from zope.component import getUtility

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.lock import IResourceLock
from seantis.reservation.lock import resource_transaction
from seantis.reservation.error import ResourceLockedError

class TestLock(IntegrationTestCase):

    def _acquire(self, resource):
        locktool = getUtility(IResourceLock)
        return locktool.acquire(resource)

    def _release(self, resource):
        locktool = getUtility(IResourceLock)
        locktool.release(resource)

    def test_lock(self):

        self.assertTrue(self._acquire('0xdeadbeef'))
        self.assertFalse(self._acquire('0xdeadbeef'))

        self.assertTrue(self._acquire('0xdeadbabe'))
        self.assertFalse(self._acquire('0xdeadbabe'))

        self._release('0xdeadbeef')

        self.assertTrue(self._acquire('0xdeadbeef'))
        self.assertFalse(self._acquire('0xdeadbeef'))
        self.assertFalse(self._acquire('0xdeadbabe'))

_lock = Lock()

class Mock(object):
    def __init__(self, resource):
        self.resource = resource

    @resource_transaction
    def wait(self):
        try:
            _lock.acquire()
        finally:
            _lock.release()

class TestThreadedLock(IntegrationTestCase):
    def test_threaded_lock(self):
        mock = Mock('threaded')

        thread = Thread(target=mock.wait)

        try:
            # Acquire the threading.Lock
            _lock.acquire()
            
            # Start the thread which will block until lock is released
            thread.start()

            # Ensure that while the thread is blocking an error is thrown
            self.assertRaises(ResourceLockedError, mock.wait)
        finally:
            # Release the lock and let the thread finish
            _lock.release()
            thread.join()

        # Call the locked function again, which should not throw an error now
        mock.wait()