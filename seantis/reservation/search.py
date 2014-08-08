from datetime import date, datetime, time
from five import grok
from plone.autoform.form import AutoExtensibleForm
from plone.directives import form
from plone.supermodel import model
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope import schema

from seantis.reservation import _
from seantis.reservation.utils import cached_property
from seantis.reservation.form import BaseForm
from seantis.reservation.resource import YourReservationsViewlet
from seantis.reservation.interfaces import IResourceBase, days as weekdays


class ISearchAndReserveForm(model.Schema):
    """ Search form for search & reserve view. """

    form.mode(timeframes='hidden')
    timeframes = schema.Text(
        title=_(u'Timeframes'),
        default=u'',
        required=False
    )

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

    form.widget(days=CheckBoxFieldWidget)
    days = schema.List(
        title=_(u"Days"),
        value_type=schema.Choice(vocabulary=weekdays),
        required=False
    )

    minspots = schema.Int(
        title=_(u"Spots"),
        required=False
    )

    available_only = schema.Bool(
        title=_(u"Available only"),
        required=False,
        default=True
    )


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
    enable_unload_protection = False

    results = None
    searched = False

    start_time = None
    end_time = None

    # show the seantis.dir.facility viewlet if it's present
    show_facility_viewlet = True

    def update(self):
        super(SearchForm, self).update()
        self.widgets['timeframes'].value = self.context.json_timeframes()

    @property
    def available_actions(self):
        yield dict(name='search', title=_(u'Search'), css_class='context')

    @cached_property
    def options(self):
        params = self.parameters

        if not params:
            return None

        options = {}

        options['days'] = tuple(d.weekday for d in params['days'])
        options['minspots'] = params['minspots'] or 0
        options['available_only'] = params['available_only']
        options['whole_day'] = params['whole_day'] and 'yes' or 'any'

        if options['whole_day'] == 'yes':
            start = datetime.combine(params['recurrence_start'], time(0, 0))
            end = datetime.combine(
                params['recurrence_end'], time(23, 59, 59, 999999)
            )
        else:
            self.start_time = params['start_time'] or time(0, 0)
            self.end_time = params['end_time'] or time(23, 59, 59, 999999)

            start = datetime.combine(
                params['recurrence_start'], self.start_time
            )
            end = datetime.combine(
                params['recurrence_end'], self.end_time
            )

        options['start'] = start
        options['end'] = end

        return options

    def handle_search(self):
        self.searched = True

        if not self.options:
            self.results = tuple()
        else:
            self.results = self.context.scheduler().search_allocations(
                **self.options
            )
