import isodate
import json

from datetime import date, datetime, time
from five import grok
from plone.directives import form
from plone.supermodel import model
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope import schema
from zope.interface import Interface
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.autoform.form import AutoExtensibleForm

from seantis.reservation import _
from seantis.reservation import db
from seantis.reservation import exposure
from seantis.reservation import utils
from seantis.reservation.base import BaseView
from seantis.reservation.form import BaseForm
from seantis.reservation import interfaces


@grok.provider(IContextSourceBinder)
def resource_choices(context):
    resources = utils.portal_type_in_context(
        context, 'seantis.reservation.resource', depth=10
    )

    choices = []

    for resource in resources:
        choices.append(
            SimpleTerm(
                value=resource.UID,
                title=utils.get_resource_title(resource.getObject())
            )
        )

    choices.sort(key=lambda c: c.title)

    return SimpleVocabulary(choices)


class ISearchAndReserveForm(model.Schema):
    """ Search form for search & reserve view. """

    recurrence_start = schema.Date(
        title=_(u"Start date"),
        required=True
    )

    recurrence_end = schema.Date(
        title=_(u"End date"),
        required=True
    )

    whole_day = schema.Bool(
        title=_(u"Whole day"),
        required=False,
        default=False
    )

    start_time = schema.Time(
        title=_(u"Start time"),
        required=False
    )

    end_time = schema.Time(
        title=_(u"End time"),
        required=False
    )

    days = schema.List(
        title=_(u"Days"),
        value_type=schema.Choice(vocabulary=interfaces.days),
        required=False
    )

    model.fieldset(
        'options',
        label=_(u"Options"),
        fields=['resources', 'free_spots', 'available_only']
    )

    resources = schema.List(
        title=_(u"Resources"),
        value_type=schema.Choice(source=resource_choices),
        required=True,
        constraint=interfaces.select_at_least_one
    )

    free_spots = schema.Int(
        title=_(u"Free spots"),
        required=False
    )

    available_only = schema.Bool(
        title=_(u"Available only"),
        required=False,
        default=False
    )

    form.widget(days=CheckBoxFieldWidget)
    form.widget(resources=CheckBoxFieldWidget)


@form.default_value(field=ISearchAndReserveForm['recurrence_start'])
def start_default(data):
    return date.today()


@form.default_value(field=ISearchAndReserveForm['recurrence_end'])
def end_default(data):
    return date.today()


class SearchAndReserve(BaseForm, AutoExtensibleForm):
    permission = 'zope2.View'

    grok.context(Interface)
    grok.require(permission)
    grok.name('search-and-reserve')

    ignoreContext = True

    template = grok.PageTemplateFile('templates/search_and_reserve.pt')
    schema = ISearchAndReserveForm

    enable_form_tabbing = False

    results = None
    searched = False

    @property
    def available_actions(self):
        return [
            dict(name='search', title=_(u'Search'), css_class='context'),
        ]

    def handle_search(self):
        self.searched = True
        self.results = self.search()

    def search(self):
        params = self.parameters

        if not params:
            return None

        resources = {}

        for resource in params['resources']:
            r = utils.get_resource_by_uuid(resource)

            resources[resource] = {
                'title': utils.get_resource_title(r.getObject()),
                'uuid': utils.string_uuid(resource),
                'url': r.getURL()
            }

        is_exposed = exposure.for_allocations(
            self.context, params['resources']
        )

        options = {}

        options['days'] = [d.weekday for d in params['days']]
        options['reservable_spots'] = params['free_spots'] or 0
        options['available_only'] = params['available_only']
        options['whole_day'] = params['whole_day'] and 'yes' or 'any'

        if options['whole_day'] == 'yes':
            start = datetime.combine(params['recurrence_start'], time(0, 0))
            end = datetime.combine(
                params['recurrence_end'], time(23, 59, 59, 999999)
            )
        else:
            start_time = params['start_time'] or time(0, 0)
            end_time = params['end_time'] or time(23, 59, 59, 999999)

            start = datetime.combine(params['recurrence_start'], start_time)
            end = datetime.combine(params['recurrence_end'], end_time)

        found = db.search_allocations(
            params['resources'], start, end,
            options=options, is_included=is_exposed
        )

        result = []

        for allocation in found:
            if hasattr(allocation, '_cached_availability'):
                availability = allocation._cached_availability
            else:
                availability = db.availability_by_range(
                    allocation.start,
                    allocation.end,
                    [allocation.resource],
                    is_exposed
                )

            availability, text, allocation_class = utils.event_availability(
                self.context,
                self.request,
                allocation,
                availability=availability
            )

            result.append({
                'resource': resources[utils.string_uuid(allocation.resource)],
                'allocation': {
                    'id': allocation.id,
                    'date': utils.display_date(
                        allocation.start, allocation.end
                    ),
                    'class': utils.event_class(availability),
                    'text': ', '.join(text.split('\n'))
                }
            })

        return result


class SearchAllocations(BaseView):
    permission = 'zope2.View'

    grok.context(Interface)
    grok.require(permission)
    grok.name('search-allocations')

    @property
    def resources(self):
        resources = self.request.get('resource')

        if isinstance(resources, basestring):
            return [resources]
        else:
            return resources

    @property
    def start(self):
        return isodate.parse_datetime(self.request.get('start'))

    @property
    def end(self):
        return isodate.parse_datetime(self.request.get('end'))

    @property
    def days(self):
        days = self.request.get('days')

        if not days:
            return None
        else:
            return days.split(',')

    @property
    def reservable_spots(self):
        return int(self.request.get('reservable_spots', 0))

    @property
    def available_only(self):
        return 'available_only' in self.request

    @property
    def whole_day(self):
        return self.request.get('whole_day', 'any')

    def render(self):
        return json.dumps(self.search())

    def search(self):
        resources = {}

        for resource in self.resources:
            r = utils.get_resource_by_uuid(resource)

            resources[resource] = {
                'title': utils.get_resource_title(r),
                'uuid': utils.string_uuid(resource),
                'url': r.getURL()
            }

        is_exposed = exposure.for_allocations(self.context, self.resources)

        options = {}
        options['days'] = self.days
        options['reservable_spots'] = self.reservable_spots
        options['available_only'] = self.available_only
        options['whole_day'] = self.whole_day

        found = db.search_allocations(
            self.resources, self.start, self.end,
            options=options, is_included=is_exposed
        )

        result = []

        for allocation in found:
            result.append({
                'resource': resources[utils.string_uuid(allocation.resource)],
                'allocation': {
                    'start': isodate.datetime_isoformat(
                        allocation.display_start
                    ),
                    'end': isodate.datetime_isoformat(
                        allocation.display_end
                    ),
                    'id': allocation.id,
                    'availability': allocation.availability
                }
            })

        return result
