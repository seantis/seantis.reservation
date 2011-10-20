"""
The session module provides the sqlalchemy session for all of seantis.reservation
Read the following doc for the why and how:

About transactions in seantis.reservation
=========================================

All sqlalchemy transactions are bound to the transactions of Zope. This is
provided by zope.sqlalchemy which ensures that both sql and zope transaction
always go hand in hand.

The sqlalchemy transactions themselves are handled by the used DB backend. In
the case of seantis.reservaiton this is either sqlite (for testing) or postgres.

Though other backends are possible these are the ones that are tried and tested.

Transaction isolation
=====================

A feature of postgres (and indeed other databases) is the ability to use varying
degrees of transaction isolation. Simply put, some transactions are less
isolated than others. 

The better the isolation, the worse the performance.

See the nice documentation on the topic in the postgres manual:
http://www.postgresql.org/docs/current/static/transaction-iso.html

Required Levels
===============

There are two levels we need for reservations. One is the Read Commited Isolation 
Level for fast database reads when browsing the calendar.

The other is the Serializable Isolation Level for database writes. This level
ensures that no two transactions are processed at the same time. Bad news for
concurrency, but very good news for integrity.

Implementation
==============

It would be nice to be able to use fast isolation when running uncritical
codepaths and good isolation during critical paths. Unfortunately sqlalchemy
(psycopg2 to be precise) does not offer any such way.

This is why the session module exists.

What it does is provide a global utility (think singleton). Which stores
a default session and a serializable isolation level session for each thread.

(It is important to have different sessions for different threads)

Usage
=====

A function which should, within it's scope, force all database requests to go
through the isolated transaction, can do so by using the @serialized decorator
or the serialized_call function. These two functions will switch the current 
thread to the serializable isolation session and back for whatever they wrap.

Since all functions get their session from the global session utility this
means that the transaction isolation can be globally switched.

It also means that one must be careful when using this feature. Mixing of
these two sessions may lead to one session not seeing what the other did.

As long as the session is not mixed within a single request though, everything
should be fine.

Testing
=======

The current sqlite tests are quite useless as sqlite does not go near the featureset
of postgres. TODO: Add a postgres test

"""
import threading

from five import grok

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from zope.interface import Interface
from zope.interface import implements
from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError

from seantis.reservation import utils
from seantis.reservation import error

def use_serial_session(dsn):
    """Returns true if the given database connection should be used with
    Serializable Transaction Isolation or not.

    """
    # Currently, only postgres+psycopg2 is supported
    if 'sqlite' in dsn:
        return False
    elif 'postgresql+psycopg2' in dsn:
        return True
    else:
        return False

class ISessionUtility(Interface):
    """Describes the interface of the session utility which provides
    all query functions with the right session.

    """

    def get_session(self):
        """Returns the session that should be used."""

    def use_main_session(self):
        """Instructs the utility to use the main session."""

    def use_serial_session(self):
        """Instructs the utility to use the isolated serializable session."""


class SessionUtility(grok.GlobalUtility):
    """Global session utility. It wraps two global session pools through which
    all database interaction (should) be flowing."""

    implements(ISessionUtility)

    def __init__(self):
        self.dsn = utils.get_config('dsn')
        self._threadstore = threading.local()

    @property
    def threadstore(self):
        store = self._threadstore

        if not hasattr(store, 'main_session'):
            store.main_session = self.create_session()

        if not hasattr(store, 'serial_session'):
            if use_serial_session(self.dsn):
                store.serial_session = self.create_session('SERIALIZABLE')
            else:
                store.serial_session = store.main_session

        if not hasattr(store, 'current_session'):
            store.current_session = store.main_session

        return store

    def create_session(self, isolation_level=None):
        if isolation_level:
            engine = create_engine(self.dsn, isolation_level=isolation_level)
        else:
            engine = create_engine(self.dsn)

        return scoped_session(sessionmaker(
            bind=engine, autocommit=False, autoflush=True,
            extension=ZopeTransactionExtension()
        ))

    def get_session(self):
        return self.threadstore.current_session

    def use_main_session(self):
        self.threadstore.current_session = self.threadstore.main_session
        return self.get_session()

    def use_serial_session(self):
        self.threadstore.current_session = self.threadstore.serial_session
        return self.get_session()

class SessionWrapper(object):
    def __getattr__(self, name):
        try:
            return getattr(getUtility(ISessionUtility).get_session(), name)
        except ComponentLookupError:
            raise AttributeError(name)

Session = SessionWrapper()

def serialized_call(fn):

    def wrapper(*args, **kwargs):
        util = getUtility(ISessionUtility)

        # sqlite has a lot of trouble with nested savepoints. Might be better
        # with python 2.7....
        if 'sqlite' in util.dsn: 
            return fn(*args, **kwargs)

        serial = util.use_serial_session()
        serial.begin_nested()
        
        try:    
            result = fn(*args, **kwargs)
            serial.flush()
            return result
        except:
            serial.rollback()
            raise    
        finally:
            util.use_main_session()
    
    return wrapper


def serialized(fn):

    def wrapper(self, *args, **kwargs):
        return serialized_call(fn)(self, *args, **kwargs)

    return wrapper
