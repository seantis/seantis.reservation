from logging import getLogger
log = getLogger('seantis.reservation')

import json
import libres
import pytz

from datetime import datetime, date

from Products.ATContentTypes.interface import IATFolder

from Acquisition import aq_inner
from five import grok
from plone import api
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from plone.app.linkintegrity.interfaces import ILinkIntegrityInfo
from plone.memoize import view
from zope.component import getUtility
from zope.event import notify
from zope.interface import implements, Interface
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from seantis.reservation import _
from seantis.reservation import exposure
from seantis.reservation import settings
from seantis.reservation import utils
from seantis.reservation.base import BaseView
from seantis.reservation.events import ResourceViewedEvent
from seantis.reservation.timeframe import timeframes_by_context
from seantis.reservation.form import AllocationGroupView, ResourceParameterView
from seantis.reservation.interfaces import IResourceBase
from seantis.reservation.interfaces import IOverview
from seantis.reservation.session import ILibresUtility


class LibresExposure(object):

    def __init__(self, fn):
        self.is_allocation_exposed = fn


def get_queries(resources):
    libres_util = getUtility(ILibresUtility)
    libres_util.context.set_service(
        'exposure',
        lambda ctx: LibresExposure(exposure.for_allocations(resources))
    )

    return libres.db.queries.Queries(libres_util.context)


class Resource(Container):

    # Do not use @property here as it messes with the acquisition context.
    # Don't know why.. it worked for me in other cases.

    def uuid(self):
        return IUUID(self)

    def string_uuid(self):
        return utils.string_uuid(self.uuid())

    def scheduler(self, language=None):
        uuid = utils.string_uuid(self.uuid())

        libres_util = getUtility(ILibresUtility)
        libres_util.context.set_service(
            'exposure',
            lambda ctx: LibresExposure(exposure.for_allocations([uuid]))
        )

        return libres_util.scheduler(uuid, settings.timezone().zone)

    def timeframes(self):
        return timeframes_by_context(self)

    def json_timeframes(self):
        results = []
        for frame in self.timeframes():
            results.append(
                dict(title=frame.title, start=frame.start, end=frame.end)
            )

        dthandler = lambda obj: \
            obj.isoformat() if isinstance(obj, date) else None
        return json.dumps(results, default=dthandler).decode('utf-8')

    def resource_title(self):
        return utils.get_resource_title(self)


@grok.subscribe(IResourceBase, IObjectRemovedEvent)
def on_removed_resource(resource, event):
    request = getattr(resource, 'REQUEST', None)

    if request is None:
        return

    info = ILinkIntegrityInfo(request)

    if info.integrityCheckingEnabled():
        if info.getIntegrityBreaches():
            return

        # info.isConfirmedItem simply does not work
        # it is really awful to have to deal with these internals

        if 'form.submitted' not in request:
            return

        if 'form.button.Cancel' in request:
            return

        if getattr(request, 'link_integrity_events_counter', 0) != 2:
            return

    log.info('extinguising resource {}'.format(resource.uuid()))
    resource.scheduler().extinguish_managed_records()


class YourReservationsViewlet(object):

    @utils.cached_property
    def your_reservations(self):

        # circular imports.. better things to do than fixing that right now..
        # grumble, grumble
        from seantis.reservation.reserve import YourReservationsViewlet

        context = aq_inner(self.context)
        viewlet = YourReservationsViewlet(context, self.request, None, None)

        if not viewlet.has_reservations:
            return ""

        viewlet.update()
        return viewlet.render()


class View(BaseView, YourReservationsViewlet):
    permission = 'zope2.View'

    grok.context(IResourceBase)
    grok.require(permission)

    template = grok.PageTemplateFile('templates/resource.pt')

    fired_event = False

    @property
    def selected_view(self):
        return self.request.get('selected_view')

    @property
    def specific_date(self):
        specific_date = self.request.get('specific_date')

        try:
            return datetime.strptime(specific_date, '%Y-%m-%d')
        except:
            return None

    def update(self, *args, **kwargs):
        super(View, self).update(*args, **kwargs)

        if not self.fired_event:
            notify(ResourceViewedEvent(self.context))
            self.fired_event = True

    @view.memoize
    def resources(self):
        uids = self.request.get('compare_to', [])
        if not hasattr(uids, '__iter__'):
            uids = [uids]

        resources = [self.context]
        for uid in uids:
            resource = utils.get_resource_by_uuid(uid)
            resources.append(resource.getObject())

        template = 'seantis-reservation-calendar-%i'
        for ix, resource in enumerate(resources):
            setattr(resource, '_v_calendar_id', template % ix)

        return resources

    def title(self, resource):
        return utils.get_resource_title(resource)

    def javascript(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis.calendars) this.seantis.calendars = [];

            %s
        </script>
        """

        resources = self.resources()
        min_h = min(r.first_hour for r in resources)
        max_h = max(r.last_hour for r in resources)

        # the view options are always the ones from the context
        available_views = self.context.available_views
        selected_view = self.context.selected_view
        selected_date = self.context.selected_date
        specific_date = self.context.specific_date

        calendars = []
        for ix, resource in enumerate(self.resources()):
            calendars.append(self.calendar_options(
                ix, resource, min_h, max_h,
                available_views, selected_view, selected_date, specific_date
            ))

        return template % '\n'.join(calendars)

    def calendar_options(
            self, ix, resource,
            first_hour=None, last_hour=None,
            available_views=None, selected_view=None,
            selected_date=None, specific_date=None):

        template = """
        this.seantis.calendars.push({
            id:'#%s',
            options:%s,
            addurl:'%s'
        })
        """
        baseurl = resource.absolute_url_path()
        addurl = baseurl + '/allocate'
        eventurl = baseurl + '/slots'

        options = {}
        options['events'] = eventurl
        options['minTime'] = first_hour or resource.first_hour
        options['maxTime'] = last_hour or resource.last_hour

        if self.selected_view in ('month', 'agendaWeek', 'agendaDay'):
            options['defaultView'] = self.selected_view
        else:
            options['defaultView'] = selected_view or resource.selected_view

        is_exposed = exposure.for_calendar(resource)
        options['selectable'] = is_exposed('selectable')
        options['editable'] = is_exposed('editable')

        options['header'] = {
            'left': 'prev, next today',
            'center': 'title',
            'right': ', '.join(available_views or resource.available_views)
        }

        if self.specific_date:
            specific_date = self.specific_date
            options['year'] = specific_date.year
            options['month'] = specific_date.month - 1  # js is off by one
            options['date'] = specific_date.day
        elif selected_date == 'specific' and specific_date:
            options['year'] = specific_date.year
            options['month'] = specific_date.month - 1  # js is off by one
            options['date'] = specific_date.day

        # localize the date display on the calendar, currently the default
        # is German (calendar.js), with english being used alternatively
        # format: http://arshaw.com/fullcalendar/docs1/utilities/formatDate/
        lang = api.portal.get_tool('portal_languages').getPreferredLanguage()

        if lang.startswith('en'):
            options['axisFormat'] = 'h:mm tt'
            options['timeFormat'] = 'h:mm tt { - h:mm tt}'
            options['columnFormat'] = {
                'month': 'ddd',
                'week': 'ddd M/d',
                'year': 'dddd M/d'
            }

        return template % (
            resource._v_calendar_id, json.dumps(options), addurl
        )

    @property
    def calendar_count(self):
        return len(self.resources())


class GroupView(BaseView, AllocationGroupView):
    permission = 'zope2.View'

    grok.context(IResourceBase)
    grok.require(permission)
    grok.name('group')

    group = None
    template = grok.PageTemplateFile('templates/group.pt')

    def update(self, **kwargs):
        self.group = self.request.get('name', u'').decode('utf-8')

    def title(self):
        return self.group


class Listing(BaseView):
    permission = 'zope2.View'
    implements(IOverview)

    grok.context(IATFolder)
    grok.require(permission)
    grok.name('resource_listing')

    template = grok.PageTemplateFile('templates/listing.pt')

    def list_item(self, item):
        return item.portal_type == 'seantis.reservation.resource'

    def resource_map(self):
        return (r.UID for r in utils.portal_type_in_context(
            self.context, 'seantis.reservation.resource'
        ))


class ThankYouPage(BaseView, ResourceParameterView):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('thank-you-for-reserving')

    template = grok.PageTemplateFile('templates/thankyoupage.pt')

    @property
    def current_url(self):
        return self.request.ACTUAL_URL + "?" + self.request.QUERY_STRING

    def infoblocks(self):
        blocks = []

        for resource in self.resources.values():
            text = (getattr(resource, 'thank_you_text', None) or u'').strip()

            if text:
                blocks.append((utils.get_resource_title(resource), text))

        return blocks


class CalendarRequest(object):

    @property
    def range(self):
        start = self.request.get('start', None)
        end = self.request.get('end', None)

        if not all((start, end)):
            return None, None

        return (
            datetime.fromtimestamp(float(start), pytz.utc),
            datetime.fromtimestamp(float(end), pytz.utc)
        )

    def render(self, **kwargs):
        start, end = self.range
        if not all((start, end)):
            return json.dumps([])

        events = self.events()

        return json.dumps(events, cls=utils.UUIDEncoder)

    def events(self):
        raise NotImplementedError


class Slots(BaseView, CalendarRequest):
    permission = 'zope2.View'

    grok.context(IResourceBase)
    grok.require(permission)
    grok.name('slots')

    def render(self):
        return CalendarRequest.render(self)

    @property
    def resource(self):
        return self.context

    @property
    def scheduler(self):
        return self.context.scheduler()

    def urls(self, allocation):
        """Returns the options for the js contextmenu for the given allocation
        as well as other links associated with the event.

        """

        items = utils.EventUrls(self.context, self.request, exposure)

        start = utils.utctimestamp(
            allocation.display_start(settings.timezone()))
        end = utils.utctimestamp(
            allocation.display_end(settings.timezone()))

        items.move_url('edit-allocation', dict(id=allocation.id))

        # Reservation
        res_add = lambda n, v, p, t: \
            items.menu_add(_(u'Reservations'), n, v, p, t)
        if allocation.is_separate:
            res_add(
                _(u'Reserve'), 'reserve',
                dict(id=allocation.id, start=start, end=end), 'overlay'
            )
            items.default_url(
                'reserve', dict(id=allocation.id, start=start, end=end)
            )
        else:
            res_add(
                _(u'Reserve'), 'reserve-group', dict(group=allocation.group),
                'overlay'
            )
            items.default_url(
                'reserve', dict(group=allocation.group)
            )

        res_add(
            _(u'Manage'), 'reservations', dict(group=allocation.group),
            'inpage'
        )

        # menu entries for single items
        entry_add = lambda n, v, p, t: \
            items.menu_add(_('Entry'), n, v, p, t)

        entry_add(
            _(u'Edit'), 'edit-allocation', dict(id=allocation.id), 'overlay'
        )

        entry_add(
            _(u'Remove'), 'remove-allocation', dict(id=allocation.id),
            'overlay'
        )

        if allocation.in_group:
            # menu entries for group items
            group_add = lambda n, v, p, t: \
                items.menu_add(_('Recurrences'), n, v, p, t)

            group_add(
                _(u'List'), 'group', dict(name=allocation.group), 'overlay'
            )

            group_add(
                _(u'Remove'), 'remove-allocation',
                dict(group=allocation.group),
                'overlay'
            )

        # view selections
        if 'agendaDay' in self.context.available_views:
            items.menu_add(
                _(u'Reservations'), _(u'Daily View'), 'view',
                dict(
                    selected_view='agendaDay',
                    specific_date=allocation.start.strftime('%Y-%m-%d')
                ), 'window'
            )

        return items

    def events(self):
        resource = self.context
        scheduler = resource.scheduler()
        translate = utils.translator(self.context, self.request)

        is_exposed = exposure.for_allocations([resource])

        # get an event for each exposed allocation
        events = []
        for alloc in scheduler.allocations_in_range(*self.range):

            if not is_exposed(alloc):
                continue

            start = alloc.display_start(settings.timezone())
            end = alloc.display_end(settings.timezone())

            # get the urls
            urls = self.urls(alloc)

            # calculate the availability for title and class
            availability, title, klass = utils.event_availability(
                resource, self.request, scheduler, alloc
            )

            if alloc.partly_available:
                partitions = alloc.availability_partitions()
            else:
                # if the allocation is not partly available there can only
                # be one partition meant to be shown as empty unless the
                # availability is zero
                partitions = [(100, availability == 0.0)]

            event_header = alloc.whole_day and translate(_(u'Whole Day'))

            events.append(dict(
                title=title,
                start=start.isoformat(),
                end=end.isoformat(),
                className=klass,
                url=urls.default,
                menu=urls.menu,
                menuorder=urls.order,
                allocation=alloc.id,
                partitions=partitions,
                group=alloc.group,
                allDay=False,
                moveurl=urls.move,
                header=event_header
            ))

        return events
