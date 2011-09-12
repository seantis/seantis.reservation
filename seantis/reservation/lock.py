from threading import Lock

from z3c.saconfig import Session

from five import grok
from zope.interface import Interface
from zope.interface import implements
from zope.component import getUtility

from seantis.reservation.error import ResourceLockedError

_lock = Lock()

def resource_transaction(fn):
    """Decorator for resource locking. Locks a class function on any class
    which has a resource property and commits the sqlalchemy transaction
    at the end.

    """
    def locker(self, *args, **kwargs):
        assert (hasattr(self, 'resource'))
        
        lock = getUtility(IResourceLock)

        try:
            if not lock.acquire(self.resource):
                raise ResourceLockedError

            return fn(self, *args, **kwargs)
        except:
            raise
        else:
            Session.commit()
        finally:
            lock.release(self.resource)

    return locker

class IResourceLock(Interface):

    def acquire(self, resource):
        """Tries to acquire a lock with the given resource. If the resource
        is already locked False is returned. If successful, True is returned.

        """

    def release(self, resource):
        """Releases the lock of the given resource.

        """

class ResourceLock(grok.GlobalUtility):
    """Locks a resource (any hashable type) in a global utility using a
    low level thread lock and a dictionary.

    """
    implements(IResourceLock)

    def __init__(self):
        self._locks = {}

    def acquire(self, resource):
        _lock.acquire()

        try:
            if resource in self._locks:
                return False
            else:
                self._locks[resource] = None
                return True

        finally:
            _lock.release()

    def release(self, resource):
        _lock.acquire()

        try:
            if resource in self._locks:
                del self._locks[resource]
        
        finally:
            _lock.release()