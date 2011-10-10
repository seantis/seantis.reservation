import json
import time
from urllib import quote
from datetime import datetime

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from plone.memoize import view
from zope import schema
from zope import interface

from seantis.reservation import utils
from seantis.reservation.db import Scheduler
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

    def parent(self):
        return self.aq_inner.aq_parent

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

    @view.memoize
    def resources(self):
        uids = self.request.get('compare_to', [])
        if not hasattr(uids, '__iter__'):
            uids = [uids]

        resources = [self.context]
        for uid in uids:
            resource = utils.get_resource_by_uuid(self.context, uid)
            resources.append(resource.getObject())

        template = 'seantis-reservation-calendar-%i'
        for ix, resource in enumerate(resources):
            setattr(resource, 'calendar_id', template % ix)

        return resources
        
    def javascript(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis.calendars) this.seantis.calendars = [];

            %s
        </script>
        """

        resources = self.resources()
        min_h = min([r.first_hour for r in resources])
        max_h = max([r.last_hour for r in resources])

        calendars = []
        for ix, resource in enumerate(self.resources()):
            calendars.append(self.calendar_options(ix, resource, min_h, max_h))

        return template % '\n'.join(calendars)

    def calendar_options(self, ix, resource, first_hour=None, last_hour=None):
        template = """
        this.seantis.calendars.push({
            id:'#%s',
            options:%s,
            allocateurl:'%s',
        })        
        """
        baseurl = resource.absolute_url_path()
        allocateurl = baseurl + '/allocate'
        eventurl = baseurl + '/slots'

        options = {}
        options['events'] = eventurl
        options['minTime'] = first_hour or resource.first_hour
        options['maxTime'] = last_hour or resource.last_hour
        
        return template % (resource.calendar_id, json.dumps(options), allocateurl)

    @property
    def calendar_count(self):
        return len(self.resources())

class GroupView(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('group')

    group = None
    template = grok.PageTemplateFile('templates/group.pt')

    def update(self, **kwargs):
        self.group = self.request.get('name', u'').decode('utf-8')

    def title(self):
        return self.group

    def allocations(self):
        if not self.group:
            return []

        scheduler = self.context.scheduler
        return scheduler.allocations_by_group(unicode(self.group))

    def event_style(self, allocation):
        #TODO remove the css from here
        color = utils.event_color(allocation.occupation_rate)
        css = "width:180px; float:left; background-color:%s; border-color:%s;"
        return css % (color, color)

    def event_title(self, allocation):
        occupation_rate = allocation.occupation_rate
        return utils.event_title(self.context, self.request, occupation_rate)

class CalendarRequest(object):

    @property
    def range(self):
        start = self.request.get('start', None)
        end = self.request.get('end', None)
        
        if not all((start, end)):
            return None, None

        start = datetime.fromtimestamp(float(start))
        end = datetime.fromtimestamp(float(end))

        return start, end

    def render(self, **kwargs):
        start, end = self.range
        if not all((start, end)):
            return json.dumps([])

        events = self.events()
        
        return json.dumps(events)

    def events(self):
        raise NotImplementedError

class Slots(grok.View, CalendarRequest):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('slots')

    def render(self):
        return CalendarRequest.render(self)

    def events(self):
        resource = self.context
        scheduler = resource.scheduler

        base = resource.absolute_url_path()
        reserve = '/reserve?start=%s&end=%s'
        edit = '/edit-allocation?id=%s'
        group = '/group?name=%s'
        remove = '/remove-allocation?id=%s'
        removegroup = '/remove-allocation?group=%s'

        events = []
        urlquote = lambda fragment: quote(unicode(fragment).encode('utf-8'))

        for alloc in scheduler.allocations_in_range(*self.range):
            start, end = alloc.display_start, alloc.display_end

            startstamp = time.mktime(start.timetuple())
            endstamp = time.mktime(end.timetuple())

            reserveurl = base + reserve % (startstamp, endstamp)
            editurl = base + edit % alloc.id
            removeurl = base + remove % alloc.id

            if alloc.in_group:
                groupurl = base + group % urlquote(alloc.group)
                removegroupurl = base + removegroup % urlquote(alloc.group)
            else:
                groupurl = None
                removegroupurl = None

            occupation_rate = alloc.occupation_rate
            color = utils.event_color(occupation_rate)
            title = utils.event_title(resource, self.request, occupation_rate)

            events.append(dict(
                allDay=False,
                start=start.isoformat(),
                end=end.isoformat(),
                title=title,
                backgroundColor=color, 
                borderColor=color,
                url=reserveurl,
                editurl=editurl,
                groupurl=groupurl,
                removeurl=removeurl,
                removegroupurl=removegroupurl,
                allocation = alloc.id,
                partitions = alloc.occupation_partitions(),
                group = alloc.group
            ))
        
        return events