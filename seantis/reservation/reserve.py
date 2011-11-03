from datetime import datetime
from datetime import timedelta

from five import grok
from zope import schema
from zope import interface
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.raster import rasterize_start
from seantis.reservation.form import (
        ResourceBaseForm, 
        extract_action_data
    )

#TODO make defaults dynamic

class IReservation(interface.Interface):

    day = schema.Date(
        title=_(u'Day')
        )

    start_time = schema.Time(
        title=_(u'Start')
        )

    end_time = schema.Time(
        title=_(u'End')
        )

    @interface.invariant
    def isValidDateRange(Reservation):
        if Reservation.start_time >= Reservation.end_time:
            raise interface.Invalid(_(u'End date before start date'))

class ReservationForm(ResourceBaseForm):
    grok.name('reserve')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        start = datetime.combine(data.day, data.start_time)
        end = datetime.combine(data.day, data.end_time)

        scheduler = self.context.scheduler()
        action = lambda: scheduler.reserve((start, end))
        redirect = self.request.response.redirect
        success = lambda: redirect(self.context.absolute_url())

        utils.handle_action(action=action, success=success)