import json
import time
from datetime import datetime

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from zope import schema
from zope import interface

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

    @property
    def calendar_options(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis) this.seantis.calendar = {};
            
            seantis.calendar.id = '#%s';
            seantis.calendar.options = %s;
            seantis.calendar.allocateurl = '%s';
        </script>
        """

        contexturl = self.context.absolute_url_path()
        allocateurl = contexturl + '/allocate'
        eventurl = contexturl + '/slots'

        options = {}
        options['events'] = eventurl
        options['minTime'] = self.context.first_hour
        options['maxTime'] = self.context.last_hour

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
        # TODO make sure that fullcalendar reports the time in utc

        start = self.request.get('start', None)
        end = self.request.get('end', None)
        
        if not all((start, end)):
            return None, None

        start = datetime.fromtimestamp(float(start))
        end = datetime.fromtimestamp(float(end))

        return start, end

    def render(self, **kwargs):
        slots = []
        start, end = self.range

        if not all((start, end)):
            return json.dumps(slots)

        scheduler = self.context.scheduler
        baseurl = self.context.absolute_url_path() + '/reserve?start=%s&end=%s'
        editurl = self.context.absolute_url_path() + '/allocation_edit?id=%i'
        groupurl = self.context.absolute_url_path() + '/group?name=%s'

        for allocation in scheduler.allocations_in_range(start, end):
            start, end = allocation.display_start, allocation.display_end
        
            url = baseurl % (
                    time.mktime(start.timetuple()),
                    time.mktime(end.timetuple()),
                )

            edit = editurl % allocation.id

            group = allocation.in_group and (groupurl % allocation.group) or None

            slots.append(
                dict(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    title=allocation.event_title(self.context, self.request),
                    allDay=False,
                    backgroundColor=allocation.event_color,
                    borderColor=allocation.event_color,
                    url=url,
                    editurl=edit,
                    groupurl=group,
                    allocation = allocation.id,
                    partitions = allocation.occupation_partitions()
                )
            )
            
        return json.dumps(slots)