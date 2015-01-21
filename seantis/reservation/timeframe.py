from datetime import datetime

from five import grok
from plone.directives import dexterity
from plone.dexterity.content import Item
from plone.memoize import view
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish
from z3c.form import button

from seantis.reservation import _
from seantis.reservation.base import BaseViewlet
from seantis.reservation.interfaces import (
    ITimeframe, OverviewletManager, ISeantisReservationSpecific
)
from seantis.reservation import utils

# TODO cache all timeframe stuff for an hour or so.. no frequent updates needed


class Timeframe(Item):
    @property
    def timestr(self):
        return ' - '.join((
            utils.localize_date(
                datetime(self.start.year, self.start.month, self.start.day),
                long_format=False
            ),
            utils.localize_date(
                datetime(self.end.year, self.end.month, self.end.day),
                long_format=False
            )
        ))

    # Can't set a property here for some odd reason. Why does it work for
    # timestr? Same in resource.py.. it does not make sense.
    def visible(self):
        workflowTool = getToolByName(self, "portal_workflow")
        status = workflowTool.getStatusOf("timeframe_workflow", self)
        return status['review_state'] == 'visible'


def validate_timeframe(context, request, data):
    overlap = overlapping_timeframe(context, data['start'], data['end'])
    if overlap:
        msg = utils.translate(
            context, request,
            _(
                u"Timeframe overlaps with '${overlap}' in the current folder",
                mapping={'overlap': overlap.title}
            ))
        utils.form_error(msg)


def timeframes_in_context(context):
    return utils.portal_type_in_context(
        context, 'seantis.reservation.timeframe'
    )


def timeframes_by_context(context):
    return utils.portal_type_by_context(
        context, 'seantis.reservation.timeframe'
    )


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


class TimeframeAddForm(dexterity.AddForm):

    permission = 'cmf.AddPortalContent'

    grok.context(ITimeframe)
    grok.layer(ISeantisReservationSpecific)
    grok.require(permission)

    grok.name('seantis.reservation.timeframe')

    @button.buttonAndHandler(_('Save'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        validate_timeframe(self.context, self.request, data)
        dexterity.AddForm.handleAdd(self, action)


class TimeframeEditForm(dexterity.EditForm):

    permission = 'cmf.ModifyPortalContent'

    grok.context(ITimeframe)
    grok.layer(ISeantisReservationSpecific)
    grok.require(permission)

    @button.buttonAndHandler(_(u'Save'), name='save')
    def handleApply(self, action):
        data, errors = self.extractData()
        validate_timeframe(self.context, self.request, data)
        dexterity.EditForm.handleApply(self, action)


class TimeframeViewlet(BaseViewlet):

    permission = 'cmf.ModifyPortalContent'

    grok.context(IFolderish)
    grok.require(permission)

    grok.name('seantis.reservation.timeframeviewlet')
    grok.viewletmanager(OverviewletManager)

    grok.order(3)

    _template = grok.PageTemplateFile('templates/timeframes.pt')

    @property
    def workflowTool(self):
        return getToolByName(self.context, "portal_workflow")

    @view.memoize
    def timeframes(self):
        frames = [t.getObject() for t in timeframes_in_context(self.context)]
        return sorted(frames, key=lambda f: f.start)

    @property
    @view.memoize
    def titles(self):
        """Returns a dict with titles keyed by review_state. The workflow-tool
        has a getTitleForStateOnType function which should do that but
        it does not return updated values for me, just some old ones.

        The listWFStatesByTitle function on the other hand contains
        the right information and I will just use that instead.

        Once this breaks I'll read the source of the workflow tool, until this
        happens I'm off to do useful things.

        """

        titles = self.workflowTool.listWFStatesByTitle()
        return dict(((t[1], t[0]) for t in titles))

    def state(self, timeframe):
        state = self.workflowTool.getStatusOf(
            "timeframe_workflow", timeframe
        )['review_state']
        title = self.titles[state]
        return state, utils.translate_workflow(
            self.context, self.request, title
        )

    def render(self, **kwargs):
        if self.context is None:
            return u''

        return self._template.render(self)

    def visible(self, frame):
        state = self.state(frame)[0]
        return state == 'visible'

    def links(self, frame=None):

        # global links
        if not frame:
            baseurl = self.context.absolute_url()
            return [(_(u'Add timeframe'),
                    baseurl + '/++add++seantis.reservation.timeframe')]

        # frame specific links
        links = []

        action_tool = getToolByName(frame, 'portal_actions')
        actions = action_tool.listFilteredActionsFor(frame)['workflow']

        for action in actions:
            if action['visible'] and action['available']:
                action['title'] = utils.translate_workflow(
                    self.context, self.request, action['title']
                )
                links.append((action['title'], action['url']))

        baseurl = frame.absolute_url()
        links.append((_(u'Edit'), baseurl + '/edit'))
        links.append((_(u'Delete'), baseurl + '/delete_confirmation'))

        return links
