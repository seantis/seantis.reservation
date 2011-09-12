from threading import Lock

from five import grok
from zope.interface import Interface
from zope.interface import implements
from zope.component import getUtility

from seantis.reservation.error import ResourceLocked

_lock = Lock()

def resource_locked(fn):
    def locker(self, *args, **kwargs):
        assert (hasattr(self, 'resource'))
        
        lock = getUtility(IResourceLock)
        try:
            if not lock.acquire(self.resource):
                raise ResourceLocked

            return fn(self, *args, **kwargs)
        finally:
            lock.release(self.resource)

    return locker

class IResourceLock(Interface):

    def acquire(self, resource_id):
        """Tries to acquire a lock with the given resource id. If the resource
        is already locked False is returned. If successful, True is returned.

        """

    def release(self, resource_id):
        """Releases the lock of the given resource id.

        """

class ResourceLock(grok.GlobalUtility):
    implements(IResourceLock)

    def __init__(self):
        self.locks = {}

    def acquire(self, resource_id):
        _lock.acquire()

        try:
            if resource_id in self.locks:
                return False
            else:
                self.locks[resource_id] = None
                return True

        finally:
            _lock.release()

    def release(self, resource_id):
        _lock.acquire()

        try:
            if resource_id in self.locks:
                del self.locks[resource_id]
        
        finally:
            _lock.release()