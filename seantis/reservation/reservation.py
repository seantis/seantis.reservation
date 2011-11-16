from datetime import timedelta
from itertools import groupby

from five import grok
from zope import schema
from zope import interface
from z3c.form import field
from z3c.form import button
from z3c.form.ptcompat import ViewPageTemplateFile
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

class IRemoveReservation(interface.Interface):

    reservation = schema.Text(
        title=_(u'Reservation'),
        required=False
        )

    start = schema.Datetime(
        title=_(u'Start'),
        required=False
        )
        
    end = schema.Datetime(
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

class ReservationRemoveForm(ResourceBaseForm):
    permission = 'cmf.ManagePortal'

    grok.name('remove-reservation')
    grok.require(permission)

    fields = field.Fields(IRemoveReservation)
    template = ViewPageTemplateFile('templates/remove_reservation.pt')
    
    label = _(u'Remove reservation')

    hidden_fields = ['reservation', 'start', 'end']
    ignore_requirements = True

    def defaults(self):
        return dict(
            reservation=unicode(self.reservation),
            start=self.start,
            end=self.end
        )

    @property
    def reservation(self):
        return self.request.get('reservation')

    @property
    def hint(self):
        if not self.timespans():
            return _(u'No such reservation')

        if self.reservation and not all((self.start, self.end)):
            return _(u'Do you really want to remove the following reservation?')
        elif self.reservation and all((self.start, self.end)):
            return _(u'Do you really want to remove '
                     u'the following timespans from the reservation?')

    def name(self):
        return utils.random_name()

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

    @property
    def reservation_title(self):
        return self.reservation

    def display_date(self, start, end):
        end += timedelta(microseconds=1)
        if start.date() == end.date():
            return start.strftime('%d.%m.%Y %H:%M - ') + end.strftime('%H:%M')
        else:
            return start.strftime('%d.%m.%Y %H:%M - ') \
                 + end.strftime('%d.%m.%Y %H:%M')

    @view.memoize
    def timespans(self):
        if self.start and self.end:
            slots = self.scheduler.reserved_slots_by_range(
                    self.reservation, self.start, self.end
                )
        else:
            slots = self.scheduler.reserved_slots(
                    self.reservation
                ).all()

        return utils.merge_reserved_slots(slots)

    def update(self, **kwargs):
        if self.id or self.group:
            self.fields['reservation'].field.default = self.reservation
            self.fields['start'].field.default = self.start
            self.fields['end'].field.default = self.end
        super(ReservationRemoveForm, self).update(**kwargs)

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

    def name(self):
        return utils.random_name()

    def title(self):
        if self.id:
            if not self.reservations():
                return _(u'No reservations for this allocation')

            return _(u'Reservations for allocation')
        else:
            if not self.reservations():
                return _(u'No reservations for this recurrence')

            return _(u'Reservations for recurrence')

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

    def display_date(self, start, end):
        end += timedelta(microseconds=1)
        if start.date() == end.date():
            return start.strftime('%d.%m.%Y %H:%M - ') + end.strftime('%H:%M')
        else:
            return start.strftime('%d.%m.%Y %H:%M - ') \
                 + end.strftime('%d.%m.%Y %H:%M')

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