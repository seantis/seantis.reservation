from zope.component import getUtility
from seantis.reservation.session import ILibresUtility


def dbsetup(context):
    scheduler = getUtility(ILibresUtility).scheduler('maintenance', 'UTC')
    scheduler.setup_database()
