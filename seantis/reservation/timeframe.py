from five import grok
from plone.directives import form, dexterity
from plone.dexterity.content import Item
from z3c.form import button
from zope import schema, interface
from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFCore.utils import getToolByName

from seantis.reservation import _
from seantis.reservation import utils

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
    pass

class TimeframeAddForm(dexterity.AddForm):
    grok.context(ITimeframe)
    grok.name('seantis.reservation.timeframe')

    @button.buttonAndHandler(_('Save'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        validate_timeframe(self.context, self.request, data)
        dexterity.AddForm.handleAdd(self, action)

class TimeframeEditForm(dexterity.EditForm):
    grok.context(ITimeframe)

    @button.buttonAndHandler(_(u'Save'), name='save')
    def handleApply(self, action):
        data, errors = self.extractData()
        validate_timeframe(self.context, self.request, data)
        dexterity.EditForm.handleApply(self, action)

def validate_timeframe(context, request, data):
    overlap = overlapping_timeframe(context, data['start'], data['end'])
    if overlap:
        msg = utils.translate(context, request, 
                _(u"Timeframe overlaps with '%s' in the current folder")
            ) % overlap.title
        utils.form_error(msg)

def overlapping_timeframe(context, start, end):
    if context.portal_type == 'seantis.reservation.timeframe':
        folder = context.aq_inner.aq_parent
    else:
        folder = context
    path = '/'.join(folder.getPhysicalPath())

    catalog = getToolByName(context, 'portal_catalog')
    results = catalog(
            portal_type='seantis.reservation.timeframe',
            path={'query': path, 'depth': 1}
        )

    for frame in (r.getObject() for r in results):
        if frame.id == context.id:
            continue

        if utils.overlaps(start, end, frame.start, frame.end):
            return frame

    return None