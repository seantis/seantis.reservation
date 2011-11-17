from five import grok

from z3c.form import field
from z3c.form import button
from z3c.form.ptcompat import ViewPageTemplateFile

from seantis.reservation.throttle import throttled
from seantis.reservation.interfaces import (
        IResourceBase,
        IReservation,
        IGroupReservation,
        IRemoveReservation
    )

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.form import (
        ResourceBaseForm, 
        AllocationGroupView,
        ReservationListView,
        extract_action_data
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
            start, end = utils.get_date_range(data.day, data.start_time, data.end_time)
            self.context.scheduler().reserve((start, end))

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class GroupReservationForm(ResourceBaseForm, AllocationGroupView):
    permission = 'zope2.View'

    grok.name('reserve-group')
    grok.require(permission)

    fields = field.Fields(IGroupReservation)
    label = _(u'Recurrance reservation')

    template = ViewPageTemplateFile('templates/reserve_group.pt')

    hidden_fields = ['group']
    ignore_requirements = True

    def defaults(self, **kwargs):
        return dict(group=self.group)

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        def reserve():
            self.context.scheduler().reserve(group=data.group)

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationRemoveForm(ResourceBaseForm, ReservationListView):
    permission = 'cmf.ManagePortal'

    grok.name('remove-reservation')
    grok.require(permission)

    fields = field.Fields(IRemoveReservation)
    template = ViewPageTemplateFile('templates/remove_reservation.pt')
    
    label = _(u'Remove reservation')

    hidden_fields = ['reservation', 'start', 'end']
    ignore_requirements = True

    show_links = False

    @property
    def reservation(self):
        return self.request.get('reservation')

    def defaults(self):
        return dict(
            reservation=unicode(self.reservation),
            start=self.start,
            end=self.end
        )

    @property
    def hint(self):
        if not self.reservations():
            return _(u'No such reservation')

        if self.reservation and not all((self.start, self.end)):
            return _(u'Do you really want to remove the following reservations?')
        
        if self.reservation and all((self.start, self.end)):
            return _(u'Do you really want to remove '
                     u'the following timespans from the reservation?')

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):

        scheduler = self.scheduler
        action = lambda: scheduler.remove_reservation(
                data.reservation, data.start, data.end
            )

        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationList(grok.View, ReservationListView):
    permission = "cmf.ManagePortal"

    grok.name('reservations')
    grok.require(permission)

    grok.context(IResourceBase)

    template = grok.PageTemplateFile('templates/reservations.pt')

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
                return _(u'No reservations for this recurrence')

            return _(u'Reservations for recurrence')