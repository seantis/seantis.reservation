from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import rrule

from five import grok
from plone.directives import form
from z3c.form import field
from z3c.form import button
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm
from zope.interface import Interface

from seantis.reservation import _
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

#TODO add validation for dates (start < end..)
#     make defaults dynamic

class IAllocateForm(Interface):

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


class AllocateForm(form.Form):
    grok.context(resource.IResource)
    grok.name('allocate')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocateForm)

    label = _(u'Resource allocation')
    description = _(u'Allocate available dates on the resource')

    ignoreContext = True

    def update(self, **kwargs):
        try:
            start = self.request.get('start')
            start = start and datetime.fromtimestamp(float(start)) or None
            end = self.request.get('end')
            end = end and datetime.fromtimestamp(float(end)) or None 

            if start and end:
                self.fields['start'].field.default = start
                self.fields['end'].field.default = end
            
        except TypeError:
            pass

        super(AllocateForm, self).update(**kwargs)

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