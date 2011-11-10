from datetime import datetime

from five import grok
from zope import schema
from zope import interface
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.form import (
        ResourceBaseForm, 
        extract_action_data
    )

from seantis.reservation.allocate import get_date_range

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

class ReservationForm(ResourceBaseForm):
    permission = 'zope2.View'

    grok.name('reserve')
    grok.require(permission)

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        start, end = get_date_range(data)

        scheduler = self.context.scheduler()
        action = lambda: scheduler.reserve((start, end))
        redirect = self.request.response.redirect
        success = lambda: redirect(self.context.absolute_url())

        utils.handle_action(action=action, success=success)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()