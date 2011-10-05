import json
import time
from datetime import datetime
from uuid import uuid4 as uuid

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName
from zope import schema
from zope import interface

from seantis.reservation import utils
from seantis.reservation import Scheduler
from seantis.reservation import _


class IResourceBase(form.Schema):

    title = schema.TextLine(
            title=_(u'Name')
        )

    description = schema.Text(
            title=_(u'Description'),
            required=False
        )

    first_hour = schema.Int(
            title=_(u'First hour of the day'),
            default=0
        )

    last_hour = schema.Int(
            title=_(u'Last hour of the day'),
            default=24
        )

    @interface.invariant
    def isValidFirstLastHour(Resource):
        in_valid_range = lambda h: 0 <= h and h <= 24
        first_hour, last_hour = Resource.first_hour, Resource.last_hour
        
        if not in_valid_range(first_hour):
            raise interface.Invalid(_(u'Invalid first hour'))

        if not in_valid_range(last_hour):
            raise interface.Invalid(_(u'Invalid last hour'))

        if last_hour <= first_hour:
            raise interface.Invalid(
                    _(u'First hour must be smaller than last hour')
                )
                     

class IResource(IResourceBase):
    pass


class Resource(Container):

    @property
    def uuid(self):
        return IUUID(self)

    @property
    def scheduler(self):
        return Scheduler(self.uuid)

class View(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    
    template = grok.PageTemplateFile('templates/resource.pt')

    calendar_id = 'seantis-reservation-calendar'

    def other_calendars(self):
        uids = self.request.get('compare_to')
        if not hasattr(uids, '__iter__'):
            uids = [uids]
        
        for uid in uids:
            resource = utils.get_resource_by_uuid(uid)
            if resource:
                yield resource.getObject()

    def calendar(self):
        return self.context

    def javascript(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis) this.seantis.calendars = [];

            %s
        </script>
        """

        calendars = [self.calendar_options(self.calendar())]

        return template % '\n'.join(calendars)

    def calendar_options(self, context):
        template = """
        this.seantis.calendars.push({
            id:'#%s',
            options:%s,
            allocateurl:'%s',
        })        
        """

        contexturl = context.absolute_url_path()
        allocateurl = contexturl + '/allocate'
        eventurl = contexturl + '/slots'

        options = {}
        options['events'] = eventurl
        options['minTime'] = context.first_hour
        options['maxTime'] = context.last_hour
        
        return template % (self.calendar_id, options, allocateurl)

class GroupView(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('group')

    group = None
    template = grok.PageTemplateFile('templates/group.pt')

    def update(self, **kwargs):
        self.group = self.request.get('name', None)

    def title(self):
        return self.group

    def allocations(self):
        if not self.group:
            return []

        scheduler = self.context.scheduler
        return scheduler.allocations_by_group(unicode(self.group))

    def event_style(self, allocation):
        #TODO remove the css from here
        color = allocation.event_color
        css = "width:180px; float:left; background-color:%s; border-color:%s;"
        return css % (color, color)

    def event_title(self, allocation):
        return allocation.event_title(self.context, self.request)

class Slots(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('slots')

    @property
    def range(self):
        start = self.request.get('start', None)
        end = self.request.get('end', None)
        
        if not all((start, end)):
            return None, None

        start = datetime.fromtimestamp(float(start))
        end = datetime.fromtimestamp(float(end))

        return start, end

    @property
    def other_resource_id(self):
        argument = self.request.get('compare_to', None)
        return argument and uuid(argument) or None

    def events(self, resource):
        scheduler = resource.scheduler

        base = resource.absolute_url_path()
        reserve = '/reserve?start=%s&end=%s'
        edit = '/edit-allocation?id=%i'
        group = '/group?name=%s'

        events = []

        for alloc in scheduler.allocations_in_range(*self.range):
            start, end = alloc.display_start, alloc.display_end

            startstamp = time.mktime(start.timetuple())
            endstamp = time.mktime(end.timetuple())

            reserveurl = base + reserve % (startstamp, endstamp)
            editurl = base + edit % alloc.id
            groupurl = alloc.in_group and (base + group % alloc.group) or None

            events.append(dict(
                allDay=False,
                start=start.isoformat(),
                end=end.isoformat(),
                title=alloc.event_title(resource, self.request),
                backgroundColor=alloc.event_color,
                borderColor=alloc.event_color,
                url=reserveurl,
                editurl=editurl,
                groupurl=groupurl,
                allocation = alloc.id,
                partitions = alloc.occupation_partitions()
            ))
        
        return events

        
    def render(self, **kwargs):
        start, end = self.range
        if not all((start, end)):
            return json.dumps([])

        events = self.events(self.context)
        
        return json.dumps(events)