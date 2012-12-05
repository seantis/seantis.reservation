from zope.component import getUtility
from sqlalchemy import create_engine
from sqlalchemy import types
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy.schema import Column
from alembic.migration import MigrationContext
from alembic.operations import Operations

from seantis.reservation.models import customtypes
from seantis.reservation.session import ISessionUtility


def upgrade_1_to_1000(setuptools):
    """ Upgrades seantis.reservation, adding modified and created dates to
    each table in the database.

    The upgrade uses alembic to create a diff between the existing database
    and the metadata.

    """

    #####################
    """
    No longer in use, needs to be rewritten to take into account that the
    session util now carries more than one database connection.

    Something like this should do:

    util = getUtility(SessionUtility)
    upgraded = []
    for site in seantis.reservation.utils.plone_sites():
        dsn util.get_dsn(site)
        if dsn in upgraded:
            continue

        upgrade(dsn)
        upgraded.append(dsn)

    Unittests would be nice too :)
    """
    #####################

    ""
    # DO NOT USE utils.get_config('dsn') here!!!!
    # engine = create_engine(
    #    utils.get_config('dsn'), isolation_level='SERIALIZABLE'
    # )
    ""

    # connection = engine.connect()
    # trans = connection.begin()

    # try:

    #     context = MigrationContext.configure(connection)
    #     diff = compare_metadata(context, ORMBase.metadata)
    #     op = Operations(context)

    #     # go through diff and execute the changes on the operations object
    #     for method, table, col in diff:
    #         assert method == 'add_column' #only works with this method!
    #         getattr(op, method)(table, col.copy())

    #     trans.commit()

    # except:
    #     trans.rollback()
    #     raise


def upgrade_to_1001(context):

    util = getUtility(ISessionUtility)
    dsn = util.get_dsn(context)

    engine = create_engine(dsn, isolation_level='SERIALIZABLE')
    connection = engine.connect()
    trans = connection.begin()
    try:
        context = MigrationContext.configure(connection)
        op = Operations(context)

        # Check whether column exists already (happens when several plone sites
        # share the same SQL DB and this upgrade step is run in each one)
        metadata = MetaData(bind=engine)
        reservations_table = Table('reservations', metadata, autoload=True)
        if 'session_id' not in reservations_table.columns:
            op.add_column(
                'reservations',
                Column('session_id', customtypes.GUID())
            )

            trans.commit()

    except:
        trans.rollback()
        raise
