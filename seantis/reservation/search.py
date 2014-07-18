from datetime import date, datetime, time
from five import grok
from plone.directives import form
from plone.supermodel import model
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope import schema

from plone.autoform.form import AutoExtensibleForm

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.form import BaseForm
from seantis.reservation.resource import YourReservationsViewlet
from seantis.reservation.interfaces import IResourceBase, days as weekdays


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
        value_type=schema.Choice(vocabulary=weekdays),
        required=False
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


@form.default_value(field=ISearchAndReserveForm['recurrence_start'])
def start_default(data):
    return date.today()


@form.default_value(field=ISearchAndReserveForm['recurrence_end'])
def end_default(data):
    return date.today()


class SearchForm(BaseForm, AutoExtensibleForm, YourReservationsViewlet):
    permission = 'zope2.View'

    grok.context(IResourceBase)
    grok.require(permission)
    grok.name('search')

    ignoreContext = True

    template = grok.PageTemplateFile('templates/search.pt')
    schema = ISearchAndReserveForm

    enable_form_tabbing = False

    results = None
    searched = False

    # show the seantis.dir.facility viewlet if it's present
    show_facility_viewlet = True

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

        scheduler = self.context.scheduler()

        found = scheduler.search_allocations(
            start, end, options=options
        )

        result = []

        for allocation in found:

            availability, text, allocation_class = utils.event_availability(
                self.context,
                self.request,
                scheduler,
                allocation
            )

            result.append({
                'id': allocation.id,
                'date': utils.display_date(
                    allocation.start, allocation.end
                ),
                'class': utils.event_class(availability),
                'text': ', '.join(text.split('\n'))
            })

        return result
