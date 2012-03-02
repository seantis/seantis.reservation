from datetime import timedelta, date, time

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
from seantis.reservation import settings
from seantis.reservation.form import (
        ResourceBaseForm, 
        AllocationGroupView,
        ReservationListView,
        extract_action_data
    )

from seantis.reservation.error import NoResultFound

class ReservationUrls(object):

    def remove_all_url(self, reservation):
        base = self.context.absolute_url()
        return base + u'/remove-reservation?reservation=%s' % reservation[0]

    def remove_part_url(self, reservation):
        base = self.context.absolute_url()
        return base + u'/remove-reservation?reservation=%s&start=%s&end=%s' % (
                reservation[0], 
                utils.timestamp(reservation[2]), 
                utils.timestamp(reservation[3]+timedelta(microseconds=1))
            )

class ReservationForm(ResourceBaseForm):
    permission = 'zope2.View'

    grok.name('reserve')
    grok.require(permission)

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    def defaults(self, **kwargs):
        return dict(id=self.id)

    def allocation(self, id):
        return self.context.scheduler().allocation_by_id(id)

    def strptime(self, value):
        if not value:
            return None

        if not isinstance(value, basestring):
            return value

        return time(*map(int, value.split(':')))

    def validate(self, data):
        try:

            # using disabled fields means we have to reset those using
            # the metadata set by ResourceBaseForm and we also need
            # to wrap the calls to data to first consult the metadata
            self.disabled_fields = self.metadata(data).keys()

            day = date(*self.get_data(data, 'day'))
            start_time = self.strptime(self.get_data(data, 'start_time'))
            end_time = self.strptime(self.get_data(data, 'end_time'))

            start, end = utils.get_date_range(day, start_time, end_time)
            if not self.allocation(data.id).contains(start, end):
                utils.form_error(_(u'Reservation out of bounds'))

            return start, end
        except NoResultFound:
            utils.form_error(_(u'Invalid reservation request'))

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):
        start, end = self.validate(data)
        autoconfirm = not self.allocation(data.id).confirm_reservation

        def reserve(): 
            token = self.context.scheduler().reserve((start, end))
            if autoconfirm:
                self.context.scheduler().confirm_reservation(token)

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def update(self, **kwargs):
        if self.id:
            if self.allocation(self.id).partly_available:
                self.disabled_fields = ['day']
            else:
                self.disabled_fields = ['day', 'start_time', 'end_time']

        super(ReservationForm, self).update(**kwargs)

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
            token = self.context.scheduler().reserve(group=data.group)

            if not settings.get('confirm_reservation'):
                self.context.scheduler().confirm_reservation(token)

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationRemoveForm(ResourceBaseForm, ReservationListView, ReservationUrls):
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


class ReservationList(grok.View, ReservationListView, ReservationUrls):
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