import json
from itertools import groupby

from five import grok
from zope import schema
from zope import interface
from z3c.form import field
from z3c.form import button
from plone.memoize import view

from seantis.reservation.throttle import throttled
from seantis.reservation.resource import IResourceBase
from seantis.reservation import db
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

class IManageReservation(interface.Interface):

    id = schema.Int(
        title=_(u'Id'),
        required=False
        )

    group = schema.Text(
        title=_(u'Group'),
        required=False
        )
        
    start = schema.Date(
        title=_(u'Start'),
        required=False
        )

    end = schema.Date(
        title=_(u'End'),
        required=False
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

        def reserve(): 
            start, end = get_date_range(data)
            self.context.scheduler().reserve((start, end))

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class ManageReservations(grok.View):
    permission = "cmf.ManagePortal"

    grok.name('reservations')
    grok.require(permission)

    grok.context(IResourceBase)

    template = grok.PageTemplateFile('templates/manage_reservations.pt')

    @property
    def id(self):
        return utils.request_id_as_int(self.request.get('id'))
      
    @property  
    def group(self):
        if 'group' in self.request:
            return unicode(self.request['group'].decode('utf-8'))
        else:
            return u''

    def title(self):
        if self.id:
            if not self.reservations():
                return _(u'No reservations for this allocation')

            return _(u'Reservations for allocation')
        else:
            if not self.reservations():
                return _(u'No reservations for this group')

            return _(u'Reserations for group')

    @view.memoize
    def reservations(self):
        scheduler = self.context.scheduler()

        if self.id:
            query = scheduler.reservations_for_allocation(self.id)
        elif self.group:
            query = scheduler.reservations_for_group(self.group)
        else:
            return None
        
        query = db.grouped_reservation_view(query)

        keyfn = lambda result: result.reservation

        results = {}
        for key, values in groupby(query, key=keyfn):
            results[key] = list(values)

        return results

class Remove(grok.View):
    permission = "cmf.ManagePortal"

    grok.context(IResourceBase)
    grok.require(permission)
    grok.name('remove-reservation')

    @property
    def reservation(self):
        return self.request.get('reservation')

    @property
    def id(self):
        return self.request.get('id')

    def render(self, **kwargs):
        scheduler = self.context.scheduler()

        result = dict(error=True, message=u'')        

        def action():
            scheduler.remove_reservation(self.reservation, self.id)

        def success():
            result['error'] = False

        def message_handler(msg):
            result['message'] = msg
        
        utils.handle_action(
                action=action, success=success, 
                message_handler=message_handler
            )
        
        return json.dumps(result)