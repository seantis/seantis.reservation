from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import rrule

from five import grok
from plone.directives import form
from z3c.form import field
from z3c.form import button
from z3c.form import interfaces
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm
from zope import interface

from z3c.saconfig import Session

from seantis.reservation.models import Allocation
from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation import resource
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import VALID_RASTER_VALUES

frequencies = SimpleVocabulary(
        [SimpleTerm(value=rrule.DAILY, title=_(u'Daily')),
         SimpleTerm(value=rrule.WEEKLY, title=_(u'Weekly')),
         SimpleTerm(value=rrule.MONTHLY, title=_(u'Monthly')),
         SimpleTerm(value=rrule.YEARLY, title=_(u'Yearly'))
        ]
    )

#TODO make defaults dynamic

class IAllocation(interface.Interface):

    id = schema.Int(
        title=_(u'Id'),
        default=-1
        )

    start = schema.Datetime(
        title=_(u'From'),
        default=rasterize_start(datetime.today(), 60)
        )

    end = schema.Datetime(
        title=_(u'To'),
        default=rasterize_start(datetime.today(), 60) + timedelta(minutes=60)
        )

    raster = schema.Choice(
        title=_(u'Raster'),
        values=VALID_RASTER_VALUES,
        default=60
        )

    recurring = schema.Bool(
        title=_(u'Recurring'),
        default=False
        )

    frequency = schema.Choice(
        title=_(u'Frequency'),
        vocabulary=frequencies
        )

    recurrence_end = schema.Date(
        title=_(u'Until'),
        default=date.today() + timedelta(days=365)
    )

    @interface.invariant
    def isValidDateRange(Allocation):
        if Allocation.start >= Allocation.end:
            raise interface.Invalid(_(u'End date before start date'))

def from_timestamp(fn):
    def converter(self, *args, **kwargs):
        try:
            date = fn(self, *args, **kwargs)
            return date and datetime.fromtimestamp(float(date)) or None
        except TypeError:
            return None

    return converter

class AllocationForm(form.Form):
    grok.context(resource.IResource)
    grok.name('allocate')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocation)

    label = _(u'Resource allocation')
    description = _(u'Allocate available dates on the resource')

    ignoreContext = True

    @property
    @from_timestamp
    def start(self):
        return self.request.get('start')

    @property
    @from_timestamp
    def end(self):
        return self.request.get('end')

    def update(self, **kwargs):
        start, end = self.start, self.end
        if start and end:
            self.fields['start'].field.default = start
            self.fields['end'].field.default = end

        super(AllocationForm, self).update(**kwargs)

    def updateWidgets(self):
        super(AllocationForm, self).updateWidgets()
        self.widgets['id'].mode = interfaces.HIDDEN_MODE

    @button.buttonAndHandler(_(u'Allocate'))
    def allocate(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start, end = data['start'], data['end']

        dates = []
        if not data['recurring']:
            dates.append((start, end))
        else:
            rule = rrule.rrule(
                    data['frequency'], 
                    dtstart=start, 
                    until=data['recurrence_end']
                )
        
            delta = end - start
            for date in rule:
                dates.append((date, date+delta))

        self.context.scheduler.allocate(dates, raster=data['raster'])
        self.request.response.redirect(self.context.absolute_url())


class AllocationEditForm(form.Form):
    grok.context(resource.IResource)
    grok.name('allocation_edit')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocation).select('id', 'start', 'end')

    label = _(u'Edit resource allocation')
    description = _(u'Edit an existing allocation')

    ignoreContext = True

    @property
    def id(self):
        return int(self.request.get('id', 0))

    @property
    @from_timestamp
    def start(self):
        return self.request.get('start', None)

    @property
    @from_timestamp
    def end(self):
        return self.request.get('end', None)

    def update(self, **kwargs):
        id, start, end = self.id, self.start, self.end

        if not id:
            self.status = utils.translate(
                    self.context, 
                    self.request, _(u'Invalid arguments')
                )
        else:
            if not all((start, end)):
                allocation = self.context.scheduler.allocation_by_id(id)
                start = allocation.start
                end = allocation.end + timedelta(microseconds=1)
            
            self.fields['id'].field.default = id
            self.fields['start'].field.default = start
            self.fields['end'].field.default = end

        super(AllocationEditForm, self).update(**kwargs)

    def updateWidgets(self):
        super(AllocationEditForm, self).updateWidgets()
        self.widgets['id'].mode = interfaces.HIDDEN_MODE

    @button.buttonAndHandler(_(u'Edit'))
    def edit(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorMessage
            return

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        self.context.scheduler.move_allocation(
                data['id'], 
                data['start'],
                data['end']
            )

        self.request.response.redirect(self.context.absolute_url())