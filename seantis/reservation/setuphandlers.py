from Products.CMFCore.utils import getToolByName
from plone.uuid.interfaces import IMutableUUID

from seantis.reservation import ORMBase
from seantis.reservation import Session
from seantis.reservation.utils import string_uuid
from seantis.reservation.session import serialized

@serialized
def dbsetup(context):
    ORMBase.metadata.create_all(Session.bind)

def migrate_uuids(context):
    """ Plone 4.1.4 comes with plone.uuid 1.0.2 which changes the uuid
    representation to not include dashes, which it previously did.

    Since these uuids are stored as strings and must be queried as such
    it is important to be able to rely on a certain representation.

    This is why this routine goes through all resources and ensures
    that their uuids do not contain dashes.

    This also means that seantis.reservation now relies on Plone 4.1.4+ and
    plone.uuid 1.0.2+ until I figure out a way to nicely work with any
    representation.

    """

    catalog = getToolByName(context, 'portal_catalog')

    resources = catalog.unrestrictedSearchResults({
        'portal_type':'seantis.reservation.resource'
    })

    for resource in resources:
        obj = resource.getObject()

        accessor = IMutableUUID(obj)
        uuid = accessor.get()

        if '-' in uuid:
            new_uuid = uuid.replace('-', '')
            
            print "uuid migration %s to %s" % (uuid, new_uuid)
            accessor.set(new_uuid)

        print "reindexing object"
        catalog.reindexObject(obj)