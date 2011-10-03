import transaction
from datetime import datetime
from datetime import timedelta

from five import grok
from zope import schema
from zope import interface
from plone.directives import form
from z3c.form import field
from z3c.form import button
from z3c.form.interfaces import ActionExecutionError
from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation import _
from seantis.reservation import resource
from seantis.reservation import error
from seantis.reservation import utils
from seantis.reservation.raster import rasterize_start

#TODO make defaults dynamic

class IReservation(interface.Interface):

    start = schema.Datetime(
        title=_(u'From'),
        default=rasterize_start(datetime.now(), 60)
        )

    end = schema.Datetime(
        title=_(u'To'),
        default=rasterize_start(datetime.today(), 60) + timedelta(minutes=60)
        )

    @interface.invariant
    def isValidDateRange(Allocation):
        if Allocation.start >= Allocation.end:
            raise interface.Invalid(_(u'End date before start date'))

class ReservationForm(form.Form):
    grok.context(resource.IResource)
    grok.name('reserve')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IReservation)

    label = _(u'Resource reservation')

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

        super(ReservationForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Reserve'))
    def reserve(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start = data['start']
        end = data['end']

        scheduler = self.context.scheduler

        try:
            scheduler.reserve(((start, end),))
            Session.flush()
        except IntegrityError:
            utils.form_error(_(u'The requested period is no longer available.'))
        
        self.request.response.redirect(self.context.absolute_url())