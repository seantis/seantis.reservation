import json
from datetime import timedelta

from five import grok
from zope.interface import Interface
from plone.uuid.interfaces import IUUID

from seantis.reservation.resource import CalendarRequest
from seantis.reservation import utils

class IOverview(Interface):

    def items(self):
        """ Returns a list of items to use for the overview. Each item must have
        a method 'resources' which returns a list of seantis.reservation.resource
        objects.

        """

class OverviewletManager(grok.ViewletManager):
    grok.context(Interface)
    grok.name('seantis.reservation.overviewletmanager')

class Overviewlet(grok.Viewlet):
    grok.context(Interface)
    grok.name('seantis.reservation.overviewlet')
    grok.require('zope2.View')
    grok.viewletmanager(OverviewletManager)

    overview_id = "seantis-overview-calendar";

    _template = u"""\
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis.overview) this.seantis.overview = {};

            this.seantis.overview.id = '#%(id)s';
            this.seantis.overview.options= %(options)s;
        </script>
        <div id="%(id)s"></div>
    """

    def uuidmap(self):
        uuids = {}
        
        for item in self.view.items:
            for resource in item.resources():
                uuid = IUUID(resource)
                uuids[uuid] = item.id

        return uuids

    def overview_url(self):
        return self.context.absolute_url_path() + '/overview'

    def calendar_options(self):

        # Put the uuidmap in the json so it can be used by overview.js
        uuidmap = self.uuidmap()

        options = {}
        options['events'] = {
            'url': self.overview_url(),
            'type': 'POST',
            'data': {
                'uuid': uuidmap.keys()
            },
            'className': 'seantis-overview-event'
        }
        options['uuidmap'] = uuidmap

        return json.dumps(options)

    def render(self):
        assert (IOverview.providedBy(self.view))

        return self._template % {
                "id": self.overview_id, 
                "options": self.calendar_options()
            }

class Overview(grok.View, CalendarRequest):
    grok.context(Interface)
    grok.name('overview')
    grok.require('zope2.View')
    
    def uuids(self):
        # The uuids are transmitted by the fullcalendar call, which seems to
        # mangle the the uuid options as follows:
        uuids = self.request.get('uuid[]', [])

        if not hasattr(uuids, '__iter__'):
            uuids = [uuids]

        return uuids

    def render(self):
        result = CalendarRequest.render(self)
        return result

    def events(self):
        """ Returns the events for the overview. """
        start, end = self.range
        if not all((start, end)):
            return []

        brains = [utils.get_resource_by_uuid(self.context, uid) for uid in self.uuids()]
        resources = [b.getObject() for b in brains]
        schedulers = [r.scheduler() for r in resources]

        if not schedulers:
            return []

        events = []

        # iterate through all days and aggregate the availability for each day
        for day in xrange(0, (end - start).days):

            # create an event which spans over an entire day
            event_start = start + timedelta(days=day)
            event_end = start + timedelta(days=day+1, microseconds=-1)

            uuids = []
            totalcount, totalavailability = 0, 0.0

            for sc in schedulers:
                count, availability = sc.availability(event_start, event_end)
                totalcount += count
                totalavailability += availability

                # add every resource that belongs the the current event
                if count > 0:
                    uuids.append(str(sc.uuid))

            if not totalcount:
                continue

            average = int(totalavailability / totalcount)
            title = u''
            events.append(dict(
                start=event_start.isoformat(),
                end=event_end.isoformat(),
                title=title,
                uuids=uuids,
                className=utils.event_class(average)
            ))

        return events