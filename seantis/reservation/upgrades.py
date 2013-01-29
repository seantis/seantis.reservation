from functools import wraps

from alembic.migration import MigrationContext
from alembic.operations import Operations

from sqlalchemy import types
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy.schema import Column

from zope.component import getUtility

from seantis.reservation import utils
from seantis.reservation.models import customtypes
from seantis.reservation.session import ISessionUtility


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

    return wrapper


@db_upgrade
def upgrade_to_1001(operations, metadata):

    # Check whether column exists already (happens when several plone sites
    # share the same SQL DB and this upgrade step is run in each one)

    reservations_table = Table('reservations', metadata, autoload=True)
    if 'session_id' not in reservations_table.columns:
        operations.add_column('reservations',
            Column('session_id', customtypes.GUID())
        )


@db_upgrade
def upgrade_1001_to_1002(operations, metadata):

    reservations_table = Table('reservations', metadata, autoload=True)
    if 'quota' not in reservations_table.columns:
        operations.add_column('reservations',
            Column('quota',
                types.Integer(), nullable=False, server_default='1'
            )
        )


@db_upgrade
def upgrade_1002_to_1003(operations, metadata):

    allocations_table = Table('allocations', metadata, autoload=True)
    if 'reservation_quota_limit' not in allocations_table.columns:
        operations.add_column('allocations',
            Column('reservation_quota_limit',
                types.Integer(), nullable=False, server_default='0'
            )
        )
