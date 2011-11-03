from datetime import date, MINYEAR, MAXYEAR

from five import grok
from plone.directives import form, dexterity
from plone.dexterity.content import Item
from plone.app.layout.viewlets.interfaces import IBelowContentBody
from plone.memoize import view
from Products.CMFCore.utils import getToolByName
from z3c.form import button
from zope import schema, interface

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
            raise interface.Invalid(_(u'End date before start date'))

class Timeframe(Item):
    @property
    def timestr(self):
        return u'%s - %s' % (
                self.start.strftime('%d.%m.%Y'),
                self.end.strftime('%d.%m.%Y')
            )

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

def timeframes_in_context(context):
    path = '/'.join(context.getPhysicalPath())
    catalog = getToolByName(context, 'portal_catalog')
    results = catalog(
            portal_type = 'seantis.reservation.timeframe',
            path={'query': path, 'depth': 1}
        )
    return results

def overlapping_timeframe(context, start, end):
    if context.portal_type == 'seantis.reservation.timeframe':
        folder = context.aq_inner.aq_parent
    else:
        folder = context
    
    frames = timeframes_in_context(folder)

    for frame in frames:
        if frame.id == context.id:
            continue

        if utils.overlaps(start, end, frame.start, frame.end):
            return frame.getObject()

    return None

class TimeframeViewlet(grok.Viewlet):

    grok.name('seantis.reservation.TimeframeViewlet')
    grok.context(form.Schema)
    grok.require('cmf.ManagePortal')
    grok.viewletmanager(IBelowContentBody)

    _template = grok.PageTemplateFile('templates/timeframes.pt')

    @view.memoize
    def timeframes(self):
        frames = [t.getObject() for t in timeframes_in_context(self.context)]
        return sorted(frames, key=lambda f: f.start)

    def state(self, timeframe):
        workflowTool = getToolByName(self.context, "portal_workflow")
        status = workflowTool.getStatusOf("timeframe_workflow", timeframe)
        return status["review_state"]

    def render(self, **kwargs):
        if self.context == None:
            return u''

        # TODO add a view for the timeframes in effect, until then
        # disable them on the resource
        if self.context.portal_type == 'seantis.reservation.resource':
            return u''
        
        return self._template.render(self)

    def visible(self, frame):
        # TODO does this work with translation?
        state = self.state(frame)
        return state == 'visible'

    def links(self, frame=None):

        # global links
        if not frame:
            baseurl = self.context.absolute_url()
            return [(_(u'Add'), 
                    baseurl + '/++add++seantis.reservation.timeframe')]
        
        # frame specific links
        links = []

        action_tool = getToolByName(frame, 'portal_actions')
        actions = action_tool.listFilteredActionsFor(frame)['workflow']
        for action in actions:
            if action['visible'] and action['available']:
                links.append((action['title'], action['url']))

        baseurl = frame.absolute_url()
        links.append((_(u'Edit'), baseurl + '/edit'))
        links.append((_(u'Delete'), baseurl + '/delete_confirmation'))
        
        return links      

class TimeFrameMask(object):
    def __init__(self, timeframe=None):
        workflowTool = getToolByName(timeframe, "portal_workflow")
        status = workflowTool.getStatusOf("timeframe_workflow", timeframe)
        
        self.visible = status["review_state"] == 'visible'
        self.start, self.end = timeframe.start, timeframe.end

def timeframes_by_context(context):
    def traverse(context):
        frames = timeframes_in_context(context)
        if frames:
            return [f.getObject() for f in frames]
        else:
            if not hasattr(context, 'portal_type'):
                return []
            if context.portal_type == 'Plone Site':
                return []
            
            parent = context.aq_inner.aq_parent
            return traverse(parent)

    return traverse(context)

def timeframe_masks(context):
    frames = timeframes_by_context(context)
    return [TimeFrameMask(f) for f in frames]