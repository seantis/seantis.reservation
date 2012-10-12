# from sqlalchemy import create_engine

# from alembic.migration import MigrationContext
# from alembic.operations import Operations
# from alembic.autogenerate import compare_metadata

# from seantis.reservation import ORMBase
# from seantis.reservation import utils

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
    # engine = create_engine(utils.get_config('dsn'), isolation_level='SERIALIZABLE')
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