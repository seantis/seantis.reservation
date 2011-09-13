import json
import time

from datetime import datetime
from datetime import timedelta

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from zope import schema

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
    def calendar_js(self):
        template = """
        <script type="text/javascript">
            (function($) {
                $(document).ready(function() {
                    $('#%s').fullCalendar(%s);
                });
            })( jQuery );
        </script>
        """

        eventurl = self.context.absolute_url_path() + '/slots'

        options = {}
        options['header'] = {
            'left':'prev, next today',
            'right':'month, agendaWeek, agendaDay'
        }
        options['defaultView'] = 'agendaWeek'
        options['timeFormat'] = 'HH:mm{ - HH:mm}'
        options['axisFormat'] = 'HH:mm{ - HH:mm}'
        options['columnFormat'] = 'dddd d.M'
        options['allDaySlot'] = False
        options['firstDay'] = 1
        options['events'] = eventurl
        options['eventRender'] = 'seantis.eventRender'

        options = json.dumps(options)
        options = options.replace(
                '"seantis.eventRender"', 
                'seantis.eventRender'
            )

        return template % (self.calendar_id, options)

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
        translate = lambda txt: utils.translate(self.context, self.request, txt)
        baseurl = self.context.absolute_url_path() + '/reserve?start=%s&end=%s'

        for allocation in scheduler.allocations_in_range(start, end):
            start, end = allocation.start, allocation.end
            rate = allocation.occupation_rate

            # TODO move colors to css

            if rate == 100:
                title = translate(_(u'Occupied'))
                color = '#a1291e' #redish
            elif rate == 0:
                title = translate(_(u'Free'))
                color = '#379a00' #greenish
            else:
                title = translate(_(u'%i%% Occupied')) % rate
                color = '#e99623' #orangeish

            # add the microsecond which is substracted on creation
            # for nicer displaying
            end += timedelta(microseconds=1)
        
            url = baseurl % (
                time.mktime(start.timetuple()),
                time.mktime(end.timetuple()),
                )
            
            slots.append(
                dict(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    title=title,
                    allDay=False,
                    backgroundColor=color,
                    borderColor=color,
                    url=url
                )
            )
            
        return json.dumps(slots)