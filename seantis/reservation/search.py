import isodate
import json

from copy import copy
from datetime import date
from five import grok
from plone.directives import form
from z3c.form import field
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.browser.radio import RadioFieldWidget
from zope import schema
from zope.interface import Interface
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

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


whole_day = SimpleVocabulary(
    [
        SimpleTerm(value='any', title=_(u'Any')),
        SimpleTerm(value='yes', title=_(u'Yes')),
        SimpleTerm(value='no', title=_(u'No')),
    ]
)


class ISearchAndReserveForm(form.Schema):
    """ Search form for search & reserve view. """

    recurrence_start = schema.Date(
        title=_(u"Start date"),
        required=True
    )

    recurrence_end = schema.Date(
        title=_(u"End date"),
        required=True
    )

    start_time = schema.Time(
        title=_(u"Start time"),
        required=True
    )

    end_time = schema.Time(
        title=_(u"End"),
        required=True
    )

    days = schema.List(
        title=_(u"Days"),
        value_type=schema.Choice(vocabulary=interfaces.days),
        required=False,
    )

    resources = schema.Choice(
        title=_(u"Resources"),
        source=resource_choices,
        required=True,
    )

    whole_day = schema.List(
        title=_(u"Whole days"),
        value_type=schema.Choice(vocabulary=whole_day),
        required=False,
    )

    available_only = schema.Bool(
        title=_(u"Available only"),
        required=False,
        default=False
    )

    reservable_spots = schema.Int(
        title=_(u"Reservable spots"),
        required=False,
        default=1
    )


@form.default_value(field=ISearchAndReserveForm['recurrence_start'])
def start_default(data):
    return date.today()


@form.default_value(field=ISearchAndReserveForm['recurrence_end'])
def end_default(data):
    return date.today()


class SearchAndReserve(BaseForm):
    permission = 'zope2.View'

    grok.context(Interface)
    grok.require(permission)
    grok.name('search-and-reserve')

    ignoreContext = True

    template = grok.PageTemplateFile('templates/search_and_reserve.pt')

    @property
    def fields(self):
        fields = field.Fields(ISearchAndReserveForm)

        # this won't work using plone.directives - with Plone I kind of
        # stopped caring and just work around these issues.
        self.set_field_widget(fields, 'days', CheckBoxFieldWidget)
        self.set_field_widget(fields, 'resources', CheckBoxFieldWidget)
        self.set_field_widget(fields, 'whole_day', RadioFieldWidget)

        return fields

    def set_field_widget(self, fields, name, widget):
        f = fields[name]
        f.field = copy(f.field)
        f.widgetFactory = widget

    @property
    def available_actions(self):
        return [
            dict(name='search', title=_(u'Search'), css_class='context'),
        ]

    def handle_search(self):
        pass


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
