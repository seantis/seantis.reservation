import logging

from alembic.migration import MigrationContext
from alembic.operations import Operations
from functools import wraps
from plone import api
from plone.dexterity.interfaces import IDexterityFTI
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from seantis.reservation import settings
from seantis.reservation import utils
from seantis.reservation.session import ILibresUtility
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import types
from sqlalchemy.schema import Column
from zope.component import getUtility


log = logging.getLogger('seantis.reservation')


def db_upgrade(fn):

    @wraps(fn)
    def wrapper(context):
        # LIBRES this should be done by libres itself
        util = getUtility(ILibresUtility)
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


def disable_upgrade():
    assert False, """ Unfortunately, you can't upgrade to this
    seantis.reservation release. Please install seantis.reservation 1.1.5 first
    and run its upgrade steps, before you install seantis.reservation 1.2.0.
    """


@db_upgrade
def upgrade_to_1001(operations, metadata):
    disable_upgrade()


@db_upgrade
def upgrade_1001_to_1002(operations, metadata):
    disable_upgrade()


@db_upgrade
def upgrade_1002_to_1003(operations, metadata):
    disable_upgrade()


def upgrade_1003_to_1004(context):
    disable_upgrade()


def upgrade_1004_to_1005(context):
    disable_upgrade()


def upgrade_1005_to_1006(context):
    disable_upgrade()


@db_upgrade
def upgrade_1007_to_1008(operations, metadata):
    disable_upgrade()


@db_upgrade
def upgrade_1008_to_1009(operations, metadata):
    disable_upgrade()


def upgrade_1009_to_1010(context):
    disable_upgrade()


def upgrade_1010_to_1011(context):
    disable_upgrade()


def upgrade_1011_to_1012(context):
    disable_upgrade()


def upgrade_1012_to_1013(context):
    disable_upgrade()


def upgrade_1013_to_1014(context):
    disable_upgrade()


def upgrade_1014_to_1015(context):
    disable_upgrade()


@db_upgrade
def upgrade_1015_to_1016(operations, metadata):
    disable_upgrade()


def upgrade_1016_to_1017(context):
    disable_upgrade()


def upgrade_1017_to_1018(context):
    disable_upgrade()


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


def upgrade_1030_to_1031(context):

    recook_css_resources(context)
    recook_js_resources(context)


def upgrade_1031_to_1032(context):
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(
        'profile-seantis.reservation:default', 'typeinfo'
    )


@db_upgrade
def upgrade_1032_to_1033(operations, metadata):
    from libres.db.models.types import JSON, UTCDateTime

    # if the quota limit has been renamed, the migration already went
    # through on this database (sites may share databases)
    allocations_table = Table('allocations', metadata, autoload=True)

    if 'quota_limit' in allocations_table.columns:
        return

    # add user-data json field to allocations
    operations.add_column(
        'allocations',
        Column('data', JSON(), nullable=True))

    # add timezone to allocations (required)
    operations.add_column(
        'allocations',
        Column('timezone', types.String()))

    # add timezone to reservations (*not* required)
    operations.add_column(
        'reservations',
        Column('timezone', types.String(), nullable=True))

    # change type to
    try:
        operations.get_bind().execute("SET timezone='UTC'")

        for table in ('allocations', 'reserved_slots', 'reservations'):
            for column in ('created', 'modified'):
                operations.alter_column(
                    table, column, type_=UTCDateTime(timezone=False))
    finally:
        operations.get_bind().execute("RESET timezone")

    operations.execute(
        "UPDATE allocations SET timezone = 'UTC'")
    operations.execute(
        "UPDATE reservations SET timezone = 'UTC' WHERE start IS NOT NULL")

    # rename reservation_quota_limit to quota_limit
    operations.alter_column(
        'allocations', 'reservation_quota_limit',
        new_column_name='quota_limit')
