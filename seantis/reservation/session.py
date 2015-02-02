import libres
import threading
import re

from five import grok
from plone import api
from seantis.reservation import utils
from sqlalchemy import create_engine
from zope.component import getUtility
from zope.event import notify
from zope.interface import implements
from zope.interface import Interface
from zope.sqlalchemy import ZopeTransactionExtension

from seantis.reservation.events import (
    ReservationsApprovedEvent,
    ReservationsDeniedEvent,
    ReservationsRevokedEvent,
    ReservationsConfirmedEvent,
    ReservationTimeChangedEvent
)


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


class ILibresUtility(Interface):
    """ Global access to libres. """

    def scheduler(name, timezone):
        pass


#
# Compatibility Shims for Libres
#
def Session():

    # LIBRES there should be a more obvious way to do this
    scheduler = getUtility(ILibresUtility).scheduler('maintenance', 'UTC')
    return scheduler.session()


def db():
    scheduler = getUtility(ILibresUtility).scheduler('maintenance', 'UTC')
    return scheduler.queries
#
#
#


class CustomScheduler(libres.db.scheduler.Scheduler):
    """ Builds on the Libres scheduler to include functions that don't fit
    the scope of Libres.

    """

    @libres.context.session.serialized
    def revoke_reservation(self, token, reason, id=None, send_email=True):
        """ Revoke a reservation and inform the user of that."""

        reason = reason or u''

        # sending the email first is no problem as it won't work if
        # an exception triggers later in the request

        reservations = self.reservations_by_token(token, id).all()
        notify(ReservationsRevokedEvent(
            reservations, utils.get_current_site_language(), reason, send_email
        ))

        self.remove_reservation(token, id)

    @libres.context.session.serialized
    def change_reservation_time(
        self, token, id, new_start, new_end, send_email=True, reason=None
    ):
        from libres.modules import events

        def trigger_email(context, reservation, old_time, new_time):
            notify(ReservationTimeChangedEvent(
                reservation=reservation,
                language=utils.get_current_site_language(),
                old_time=old_time,
                new_time=new_time,
                send_email=send_email,
                reason=reason or u'',
            ))

        if send_email:
            events.on_reservation_time_changed.append(trigger_email)

        try:
            super(CustomScheduler, self).change_reservation_time(
                token, id, new_start, new_end
            )
        finally:
            if send_email:
                events.on_reservation_time_changed.remove(trigger_email)


class LibresUtility(grok.GlobalUtility):

    implements(ILibresUtility)

    def __init__(self):
        self.reset()
        self.setup_event_translation()

    def setup_event_translation(self):
        """ Libres events are different from the old seantis.reservation
        events. To ease the migration to libres, these events are translated
        here, where possible.

        """
        from libres.modules import events

        translated_events = (
            'on_reservations_approved',
            'on_reservations_denied',
            'on_reservations_confirmed'
        )

        for event in translated_events:
            libres_event = getattr(events, event)
            translation = getattr(self, event)

            if translation not in libres_event:
                libres_event.append(translation)

    def on_reservations_approved(self, context, reservations):
        notify(ReservationsApprovedEvent(
            reservations, utils.get_current_site_language()
        ))

    def on_reservations_denied(self, context, reservations):
        notify(ReservationsDeniedEvent(
            reservations, utils.get_current_site_language()
        ))

    def on_reservations_confirmed(self, context, reservations, session_id):
        notify(ReservationsConfirmedEvent(
            reservations, utils.get_current_site_language()
        ))

    def reset(self):
        self._dsn_cache = {}
        self._dsn_cache_lock = threading.Lock()

        try:
            self._default_dsn = utils.get_config('dsn')
        except utils.ConfigurationError:
            raise utils.ConfigurationError('No database configuration found.')

    def session_provider(self, context):
        return libres.context.session.SessionProvider(
            context.get_setting('dsn'),
            session_config={
                'extension': ZopeTransactionExtension()
            },
            engine_config={
                'json_serializer': utils.json_dumps,
                'json_deserializer': utils.json_loads
            }
        )

    def uuid_generator_factory(self, context):
        def uuid_generator(name):
            # since the name in seantis.reservation is always
            # the uuid of a resource, we don't need to generate
            # another one based on it
            return name
        return uuid_generator

    @property
    def context(self):
        site = api.portal.get()
        context_id = 'seantis.reservation' + '.'.join(site.getPhysicalPath())

        if not libres.registry.is_existing_context(context_id):
            context = libres.registry.register_context(context_id)
            context.set_service('session_provider', self.session_provider)
            context.set_setting('dsn', self.get_dsn(site))
            context.set_service('uuid_generator', self.uuid_generator_factory)
        else:
            context = libres.registry.get_context(context_id)

        return context

    def scheduler(self, name, timezone):
        return CustomScheduler(self.context, name, timezone)

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
