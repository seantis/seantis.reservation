import logging
log = logging.getLogger('seantis.reservation')

from functools import wraps

from alembic.migration import MigrationContext
from alembic.operations import Operations

from sqlalchemy import types
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import not_
from sqlalchemy.schema import Column

from plone import api
from plone.registry.interfaces import IRegistry
from plone.dexterity.interfaces import IDexterityFTI
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility

from seantis.reservation import Session
from seantis.reservation import utils
from seantis.reservation import settings
from seantis.reservation.models import Reservation, ReservedSlot
from seantis.reservation.models import customtypes
from seantis.reservation.session import (
    ISessionUtility,
    serialized
)


def db_upgrade(fn):

    @wraps(fn)
    def wrapper(context):
        util = getUtility(ISessionUtility)
        dsn = util.get_dsn(utils.getSite())

        engine = create_engine(dsn, isolation_level='SERIALIZABLE')
        connection = engine.connect()
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            operations = Operations(context)

            metadata = MetaData(bind=engine)

            fn(operations, metadata)

            transaction.commit()

        except:
            transaction.rollback()
            raise

        finally:
            connection.close()

    return wrapper


def recook_js_resources(context):
    getToolByName(context, 'portal_javascripts').cookResources()


def recook_css_resources(context):
    getToolByName(context, 'portal_css').cookResources()


def add_new_email_template(context, new_template):
    # go through all email templates

    from seantis.reservation.mail_templates import templates
    template = templates[new_template]

    brains = utils.portal_type_in_site('seantis.reservation.emailtemplate')

    for tpl in (b.getObject() for b in brains):

        # and add the new email template in the correct language if available
        if template.is_translated(tpl.language):
            lang = tpl.language
        else:
            lang = 'en'

        setattr(
            tpl, '{}_subject'.format(new_template), template.get_subject(lang)
        )
        setattr(
            tpl, '{}_content'.format(new_template), template.get_body(lang)
        )


def remove_dead_resources(context):
    registries = [
        getToolByName(context, 'portal_javascripts'),
        getToolByName(context, 'portal_css')
    ]

    is_managed_resource = lambda r: '++seantis.reservation' in r.getId()

    def is_dead_resource(resource):

        if resource.isExternalResource():
            return False

        if context.restrictedTraverse(resource.getId(), False):
            return False

        return True

    for registry in registries:
        for resource in registry.getResources():
            if is_managed_resource(resource):
                if is_dead_resource(resource):
                    registry.unregisterResource(resource.getId())


@db_upgrade
def upgrade_to_1001(operations, metadata):

    # Check whether column exists already (happens when several plone sites
    # share the same SQL DB and this upgrade step is run in each one)

    reservations_table = Table('reservations', metadata, autoload=True)
    if 'session_id' not in reservations_table.columns:
        operations.add_column(
            'reservations', Column('session_id', customtypes.GUID())
        )


@db_upgrade
def upgrade_1001_to_1002(operations, metadata):

    reservations_table = Table('reservations', metadata, autoload=True)
    if 'quota' not in reservations_table.columns:
        operations.add_column(
            'reservations', Column(
                'quota', types.Integer(), nullable=False, server_default='1'
            )
        )


@db_upgrade
def upgrade_1002_to_1003(operations, metadata):

    allocations_table = Table('allocations', metadata, autoload=True)
    if 'reservation_quota_limit' not in allocations_table.columns:
        operations.add_column(
            'allocations', Column(
                'reservation_quota_limit',
                types.Integer(), nullable=False, server_default='0'
            )
        )


def upgrade_1003_to_1004(context):

    # 1004 untangles the dependency hell that was default <- sunburst <- izug.
    # Now, sunburst and izug.basetheme both have their own profiles.

    # Since the default profile therefore has only the bare essential styles
    # it needs to be decided on upgrade which theme was used, the old css
    # files need to be removed and the theme profile needs to be applied.

    # acquire the current theme
    skins = getToolByName(context, 'portal_skins')
    theme = skins.getDefaultSkin()

    # find the right profile to use
    profilemap = {
        'iZug Base Theme': 'izug_basetheme',
        'Sunburst Theme': 'sunburst'
    }

    if theme not in profilemap:
        log.info("Theme %s is not supported by seantis.reservation" % theme)
        profile = 'default'
    else:
        profile = profilemap[theme]

    # remove all existing reservation stylesheets
    css_registry = getToolByName(context, 'portal_css')
    stylesheets = css_registry.getResourcesDict()
    ids = [i for i in stylesheets if 'resource++seantis.reservation.css' in i]

    map(css_registry.unregisterResource, ids)

    # reapply the chosen profile

    setup = getToolByName(context, 'portal_setup')
    setup.runAllImportStepsFromProfile(
        'profile-seantis.reservation:%s' % profile
    )


def upgrade_1004_to_1005(context):

    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'typeinfo'
    )


def upgrade_1005_to_1006(context):

    # remove the old custom fullcalendar settings
    js_registry = getToolByName(context, 'portal_javascripts')

    old_definitions = [
        '++resource++seantis.reservation.js/fullcalendar.js',
        '++resource++collective.js.fullcalendar/fullcalendar.min.js',
        '++resource++collective.js.fullcalendar/fullcalendar.gcal.js'
    ]
    map(js_registry.unregisterResource, old_definitions)

    js_registry.cookResources()

    # reapply the fullcalendar profile
    setup = getToolByName(context, 'portal_setup')

    setup.runAllImportStepsFromProfile(
        'profile-collective.js.fullcalendar:default'
    )

    recook_css_resources(context)


@db_upgrade
def upgrade_1007_to_1008(operations, metadata):

    allocations_table = Table('allocations', metadata, autoload=True)
    if 'waitinglist_spots' in allocations_table.columns:
        operations.drop_column('allocations', 'waitinglist_spots')


@db_upgrade
def upgrade_1008_to_1009(operations, metadata):

    allocations_table = Table('allocations', metadata, autoload=True)
    if 'approve_manually' not in allocations_table.columns:
        operations.alter_column(
            table_name='allocations',
            column_name='approve',
            new_column_name='approve_manually',
            server_default='FALSE'
        )


def upgrade_1009_to_1010(context):

    site = utils.getSite()
    all_resources = utils.portal_type_in_context(
        site, 'seantis.reservation.resource', depth=100
    )

    for brain in all_resources:
        resource = brain.getObject()
        resource.approve_manually = resource.approve


def upgrade_1010_to_1011(context):

    # rename fullcalendar.css to base.css
    css_registry = getToolByName(context, 'portal_css')
    css_registry.unregisterResource(
        '++resource++seantis.reservation.css/fullcalendar.css'
    )

    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'cssregistry'
    )


def upgrade_1011_to_1012(context):
    add_new_email_template(context, 'reservation_made')


def upgrade_1012_to_1013(context):
    # rerun javascript step to import URI.js
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'jsregistry'
    )


def upgrade_1013_to_1014(context):
    # rerun javascript step to fix URI.js compression
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'jsregistry'
    )


def upgrade_1014_to_1015(context):
    # rerun javascript step to fix URI.js compression
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'rolemap'
    )


@db_upgrade
def upgrade_1015_to_1016(operations, metadata):
    operations.alter_column('allocations', 'mirror_of', nullable=False)


def upgrade_1016_to_1017(context):
    fti = getUtility(IDexterityFTI, name='seantis.reservation.resource')

    # keep the behaviors, only change the actions
    behaviors = fti.behaviors

    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'typeinfo'
    )

    fti.behaviors = behaviors


@serialized
def upgrade_1017_to_1018(context):

    # seantis.reservation before 1.0.12 left behind reserved slots when
    # removing reservations of expired sessions. These need to be cleaned for
    # the allocation usage to be right.

    # all slots need a connected reservation
    all_reservations = Session.query(Reservation)

    # orphan slots are therefore all slots..
    orphan_slots = Session.query(ReservedSlot)

    # ..with tokens not found in the reservations table
    orphan_slots = orphan_slots.filter(
        not_(
            ReservedSlot.reservation_token.in_(
                all_reservations.with_entities(Reservation.token).subquery()
            )
        )
    )

    log.info(
        'Removing {} reserved slots  with no linked reservations'.format(
            orphan_slots.count()
        )
    )

    orphan_slots.delete('fetch')


def upgrade_1018_to_1019(context):
    fti = getUtility(IDexterityFTI, name='seantis.reservation.resource')

    # keep the behaviors, only change the actions
    behaviors = fti.behaviors

    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'typeinfo'
    )

    fti.behaviors = behaviors


def upgrade_1019_to_1020(context):

    # add new registry values
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'plone.app.registry'
    )


def upgrade_1020_to_1021(context):

    send_email_to_managers = settings.get('send_email_to_managers')

    registry = getUtility(IRegistry)
    registry.registerInterface(settings.ISeantisReservationSettings)

    if send_email_to_managers is True:
        settings.set('send_email_to_managers', 'by_path')
    elif send_email_to_managers is False:
        settings.set('send_email_to_managers', 'never')

    # ensure that the records exist now
    settings.get('manager_email')
    settings.get('send_email_to_managers')


def upgrade_1021_to_1022(context):

    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'browserlayer'
    )


def upgrade_1022_to_1023(context):

    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'sharing'
    )
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'rolemap'
    )


def upgrade_1023_to_1024(context):
    recook_css_resources(context)
    recook_js_resources(context)


def upgrade_1024_to_1025(context):
    recook_css_resources(context)


def upgrade_1025_to_1026(context):

    registry = getUtility(IRegistry)
    registry.registerInterface(settings.ISeantisReservationSettings)

    settings.set('available_threshold', 75)
    settings.set('partly_available_threshold', 1)

    # ensure that the records exist now
    settings.get('available_threshold')
    settings.get('partly_available_threshold')


def upgrade_1026_to_1027(context):

    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'jsregistry'
    )

    recook_js_resources(context)


def upgrade_1027_to_1028(context):

    upgrade_1026_to_1027(context)  # it's the same thing all over again
    recook_css_resources(context)


def upgrade_1028_to_1029(context):

    recook_css_resources(context)
    recook_js_resources(context)


def upgrade_1029_to_1030(context):

    add_new_email_template(context, 'reservation_time_changed')
