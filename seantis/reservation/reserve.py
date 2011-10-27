from datetime import datetime
from datetime import timedelta

from five import grok
from zope import schema
from zope import interface
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import resource
from seantis.reservation import utils
from seantis.reservation.raster import rasterize_start
from seantis.reservation.form import ResourceBaseForm, extract_action_data

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

class ReservationForm(ResourceBaseForm):
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
    @extract_action_data
    def reserve(self, data):

        scheduler = self.context.scheduler()
        action = lambda: scheduler.reserve((data.start, data.end))
        redirect = self.request.response.redirect
        success = lambda: redirect(self.context.absolute_url())

        utils.handle_action(action=action, success=success)