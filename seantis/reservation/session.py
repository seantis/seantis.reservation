"""
The session module provides the sqlalchemy session for all of
seantis.reservation

Read the following doc for the why and how:

About transactions in seantis.reservation
=========================================

All sqlalchemy transactions are bound to the transactions of Zope. This is
provided by zope.sqlalchemy which ensures that both sql and zope transaction
always go hand in hand. Namely, when the zope transaction is commited, the
sqlalchemy transaction is commited (or rolled back) at the same time.

Transaction isolation
=====================

A feature of postgres (and indeed other databases) is the ability to use
varying degrees of transaction isolation. Simply put, some transactions are
less isolated than others.

The better the isolation, the worse the performance.

See the nice documentation on the topic in the postgres manual:
http://www.postgresql.org/docs/current/static/transaction-iso.html

Required Levels
===============

There are two levels we need for reservations. One is the Read Commited
Isolation Level for fast database reads when browsing the calendar.

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
a read session and a write session for each thread. The read session uses
read commited mode, the write session serializable mode.

Usage
=====

A function which should, within it's scope, force all database requests to go
through the isolated transaction, can do so by using the @serializable
decorator or the serializable_call function. These two functions will switch
the current thread to the serializable isolation session and back for whatever
they wrap.

Since all functions get their session from the global session utility this
means that the transaction isolation can be globally switched.

It also means that one must be careful when using this feature. Mixing of
these two sessions may lead to one session not seeing what the other did.

As long as the session is not mixed within a single request though, everything
should be fine.

Note that there are hooks in place which enforce correct usage. A read session
cannot be used anymore once a serial session was used to change the database.

Testing
=======

All testing is done in test_session.py using postgres. As only postgres 9.1+
supports true serialized isolation it is a requirement to use this database.

Other databases like Oracle support this as well, but for other databases to be
supported they need to be tested first!

"""
import re
import threading
import functools

from five import grok

from sqlalchemy import create_engine
from sqlalchemy.pool import SingletonThreadPool
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from zope.interface import Interface
from zope.interface import implements
from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError

from seantis.reservation import error
from seantis.reservation import utils

from sqlalchemy import event

SERIALIZABLE = 'SERIALIZABLE'
READ_COMMITTED = 'READ_COMMITTED'


def get_postgres_version(dsn):
    """ Returns the postgres version in a tuple with the first value being
    the major version, the second being the minor version.

    Uses it's own connection to be independent from any session.

    """
    assert 'postgres' in dsn, "Not a postgres database"

    engine = create_engine(dsn)
    version = engine.execute('select version()').fetchone()[0]
    engine.dispose()

    version = re.findall('PostgreSQL (.*?) on', version)[0]
    return map(int, version.split('.'))[:2]


def assert_dsn(dsn):
    assert dsn, "Database connection not found (database.cfg)"

    if 'test://' in dsn:
        return dsn

    assert 'postgresql+psycopg2' in dsn, \
        "Only PostgreSQL combined with psycopg2 is supported"

    major, minor = get_postgres_version(dsn)

    assert (major >= 9 and minor >= 1) or (major >= 10), \
        "PostgreSQL 9.1+ is required. Your version is %i.%i" % (major, minor)

    return dsn


class ISessionUtility(Interface):
    """Describes the interface of the session utility which provides
    all query functions with the right session.

    """

    def session(self):
        """Returns the session that should be used."""

    def use_readonly(self):
        """Instructs the utility to enable the readonly session."""

    def use_serial(self):
        """Instructs the utility to use the isolated serializable session."""

    def is_serial(self):
        """Returns true if the current session is the serial session."""


class SessionStore(object):

    def __init__(self, dsn):
        self.readonly = self.create_session(READ_COMMITTED, dsn)
        self.serial = self.create_session(SERIALIZABLE, dsn)
        self.current = self.readonly

    def create_session(self, isolation_level, dsn):
        """Creates a session with the given isolation level.

        If the isolation level is serializable (writeable) a hook is created
        which will mark the session as used once it is flushed, as unused when
        the session is commited or rolledback.

        If the isolation level is read commited (readonly) a hook is created
        which will ensure that the readonly session cannot be used to flush
        changes to the database by raising ModifiedReadOnlySession if
        there are detected changes about to be flushed.

        """

        engine = create_engine(
            dsn,
            poolclass=SingletonThreadPool,
            isolation_level=isolation_level
        )

        session = scoped_session(sessionmaker(
            bind=engine, autocommit=False, autoflush=True,
            extension=ZopeTransactionExtension()
        ))

        if isolation_level == READ_COMMITTED:

            def guard_changes(session, *args):
                changelists = [session.dirty, session.deleted, session.new]

                # sum up the len of all changelists
                if sum(map(len, changelists)):
                    raise error.ModifiedReadOnlySession

            event.listen(session, 'before_flush', guard_changes)

        if isolation_level == SERIALIZABLE:

            def reset_serial(session, *args):
                session._was_used = False

            def mark_serial(session, *args):
                session._was_used = True

            event.listen(session, 'after_commit', reset_serial)
            event.listen(session, 'after_rollback', reset_serial)
            event.listen(session, 'after_soft_rollback', reset_serial)
            event.listen(session, 'after_flush', mark_serial)

        return session


class SessionUtility(grok.GlobalUtility):
    """Global session utility. It wraps two global sessions through which
    all database interaction (should) be flowing.

    As a global utility this object is present only once per Zope instance,
    so it needs to be aware of different threads.
    """

    implements(ISessionUtility)

    def __init__(self):
        self._reset_sessions()

    def _reset_sessions(self):
        """ Resets the session and threadstore. Useful for testing. """

        # Session information is stored independently for each thread.
        # SQLAlchemy does provide this in a way with scoped_session, but
        # it seems sane to be independent here
        self._threadstore = threading.local()
        self._dsn_cache = {}
        self._dsn_cache_lock = threading.Lock()

        try:
            self._default_dsn = utils.get_config('dsn')
        except utils.ConfigurationError:
            raise utils.ConfigurationError('No database configuration found.')

    def get_dsn(self, site):
        """ Returns the DSN for the given site. Will look for those dsns
        in the zope.conf which is preferrably modified using buildout's
        <product-config> construct. See database.cfg.example for more info.

        """
        site_id = site and site.id or '__no_site__'

        if site_id not in self._dsn_cache:
            specific = utils.get_config('dsn-%s' % site_id)

            assert (specific or self._default_dsn), \
                "no dsn config found, did you define a dsn in database.cfg?"

            dsn = (specific or self._default_dsn).replace('{*}', site_id)

            self._dsn_cache_lock.acquire()
            try:
                self._dsn_cache[site_id] = assert_dsn(dsn)
            finally:
                self._dsn_cache_lock.release()

        return self._dsn_cache[site_id]

    @property
    def sessionstore(self):
        """Returns the current sessionstore which will be populated with
        sessions if they are not yet present.

        """
        dsn = self.get_dsn(utils.getSite())

        if not hasattr(self._threadstore, 'sessions'):
            self._threadstore.sessions = {}

        if dsn not in self._threadstore.sessions:
            self._threadstore.sessions[dsn] = SessionStore(dsn)

        return self._threadstore.sessions[dsn]

    @property
    def is_serial(self):
        return self.sessionstore.current is self.sessionstore.serial

    @property
    def is_readonly(self):
        return self.sessionstore.current is self.sessionstore.readonly

    def is_serial_dirty(self, reset=False):
        """Returns true if the serial session was used (flushed). False if
        it was reset (rollback, commited).

        The idea is to indicate when the serial session has access to
        uncommited data which will be invisible to the readonly session.

        """
        serial = self.sessionstore.serial.registry()
        dirty = hasattr(serial, '_was_used') and serial._was_used

        if dirty and reset:
            serial._was_used = False

        return dirty

    def session(self):
        """ Return the current session. Raises DirtyReadOnlySession if the
        session to be returned is read only and the serial session was used.

        The readonly session at this point would not see uncommitted changes.
        The serial session would, but it should not be used for that if
        possible, since every read on the serial session spreads the possible
        locks within the postgres database.

        If information is needed after using the serial session, either cache
        what you need before flushing (if you need stuff which is only in the
        serial session at the time). Or use the read session before using the
        serial session (which leads to the same result in a way, but is
        explicit).

        """
        if self.is_readonly and self.is_serial_dirty(reset=True):
            raise error.DirtyReadOnlySession

        return self.sessionstore.current

    def use_readonly(self):
        self.sessionstore.current = self.sessionstore.readonly
        return self.sessionstore.current

    def use_serial(self):
        self.sessionstore.current = self.sessionstore.serial
        return self.sessionstore.current


class SessionWrapper(object):
    """ The global session wrapper utility which acts as a replacement for
    the session_maker factory. Will return the same session for any calls
    done within the same thread.

    To get a new session use seantis.reservation.Session()

    """
    def __getattr__(self, name):
        try:
            return getattr(getUtility(ISessionUtility).session(), name)
        except ComponentLookupError:
            raise AttributeError(name)

Session = SessionWrapper()


def serialized(fn):
    """ Wrapper function which wraps any function with a serial session.
    All methods called by this wrapped function will uuse the serial session.

    (Provided they are using seantis.reservation.Session and not some other
    means of talking to the database).

    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        util = getUtility(ISessionUtility)

        current = util.sessionstore.current
        serial = util.use_serial()

        try:
            result = fn(*args, **kwargs)
            serial.flush()
            serial.expire_all()
            return result
        finally:
            util.sessionstore.current = current

    return wrapper
