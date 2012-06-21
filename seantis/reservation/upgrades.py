from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.session import serialized

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.autogenerate import compare_metadata

from StringIO import StringIO

from sqlalchemy import create_engine
from sqlalchemy import Column
from sqlalchemy import types

from seantis.reservation import utils
import transaction

def upgrade_1_to_1000(setuptools):

    engine = create_engine(utils.get_config('dsn'),
        isolation_level='SERIALIZABLE'
    )
    connection = engine.connect()
    trans = connection.begin()

    try:
        context = MigrationContext.configure(connection, opts=dict(output_buffer=StringIO()))
        diff = compare_metadata(context, ORMBase.metadata)
        op = Operations(context)

        for method, table, col in diff:
            getattr(op, method)(table, col.copy())
    
        trans.commit()
    except:
        trans.rollback()
        raise