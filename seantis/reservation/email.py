from zope.schema import TextLine

from zope.interface import Invalid

from Products.CMFDefault.utils import checkEmailAddress
from Products.CMFDefault.exceptions import EmailAddressInvalid

from seantis.reservation import _

# TODO -> Move this to a separate module as it is also used in seantis.dir.base
def validate_email(value):
    try:
        if value:
            checkEmailAddress(value)
    except EmailAddressInvalid:
        raise Invalid(_(u'Invalid email address'))
    return True

class EmailField(TextLine):

    def __init__(self, *args, **kwargs):
        super(TextLine, self).__init__(*args, **kwargs)

    def _validate(self, value):
        super(TextLine, self)._validate(value)
        validate_email(value)

# referenced by configuration.zcml to register the Email fields
from plone.schemaeditor.fields import FieldFactory
EmailFieldFactory = FieldFactory(EmailField, _(u'Email'))

from plone.supermodel.exportimport import BaseHandler
EmailFieldHandler = BaseHandler(EmailField)