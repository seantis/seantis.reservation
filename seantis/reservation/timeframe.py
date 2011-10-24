from plone.directives import form
from plone.dexterity.content import Item

from zope import schema
from zope import interface

from seantis.reservation import _

class ITimeframe(form.Schema):

    title = schema.TextLine(
            title=_(u'Name')
        )

    start = schema.Date(
            title=_(u'Start')
        )

    end = schema.Date(
            title=_(u'End')
        )

    @interface.invariant
    def isValidDateRange(Timeframe):
        if Timeframe.start > Timeframe.end:
            raise interface.Invalid(_(u'Start date before end date'))

class Timeframe(Item):

    def parent(self):
        return self.aq_inner.aq_parent