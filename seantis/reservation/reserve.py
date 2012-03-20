from datetime import date, time

from five import grok

from plone.dexterity.interfaces import IDexterityFTI
from zope.component import queryUtility

from z3c.form import field
from z3c.form import button
from z3c.form import group
from z3c.form.ptcompat import ViewPageTemplateFile

from seantis.reservation.throttle import throttled
from seantis.reservation.interfaces import (
        IResourceBase,
        IReservation,
        IGroupReservation,
        IRemoveReservation,
        IApproveReservation,
    )

from seantis.reservation.error import DirtyReadOnlySession
from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.form import (
        ResourceBaseForm, 
        AllocationGroupView,
        ReservationListView,
        extract_action_data
    )

from seantis.reservation.error import NoResultFound

class ReservationUrls(object):

    def remove_all_url(self, token):
        base = self.context.absolute_url()
        return base + u'/remove-reservation?reservation=%s' % token

    def approve_all_url(self, token):
        base = self.context.absolute_url()
        return base + u'/approve-reservation?reservation=%s' % token

    def deny_all_url(self, token):
        base = self.context.absolute_url()
        return base + u'/deny-reservation?reservation=%s' % token

class ReservationSchemata(object):

    @property
    def additionalSchemata(self):
        scs = []
        self.fti = dict()

        for ptype in self.context.formsets:
             fti = queryUtility(IDexterityFTI, name=ptype)
             if fti:
                schema = fti.lookupSchema()
                scs.append((ptype, fti.title, schema))
                
                self.fti[ptype] = (fti.title, schema)

        return scs

class ReservationForm(ResourceBaseForm, ReservationSchemata):
    permission = 'zope2.View'

    grok.name('reserve')
    grok.require(permission)

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    fti = None

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    @property
    def additionalSchemata(self):
        scs = []
        self.fti = dict()

        for ptype in self.context.formsets:
             fti = queryUtility(IDexterityFTI, name=ptype)
             if fti:
                schema = fti.lookupSchema()
                scs.append((ptype, fti.title, schema))
                
                self.fti[ptype] = (fti.title, schema)

        return scs

    @property
    def disabled_fields(self):
        disabled = ['day']
        try:
            if self.id and not self.allocation(self.id).partly_available:
                disabled = ['day', 'start_time', 'end_time']
        except DirtyReadOnlySession:
            pass

        return disabled

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

            day = self.get_data(data, 'day')
            if hasattr(day, '__iter__'):
                day = date(*self.get_data(data, 'day'))

            start_time = self.strptime(self.get_data(data, 'start_time'))
            end_time = self.strptime(self.get_data(data, 'end_time'))

            start, end = utils.get_date_range(day, start_time, end_time)
            if not self.allocation(data['id']).contains(start, end):
                utils.form_error(_(u'Reservation out of bounds'))

            return start, end
        except NoResultFound:
            utils.form_error(_(u'Invalid reservation request'))

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):
        
        start, end = self.validate(data)
        autoapprove = not self.allocation(data['id']).approve

        def reserve(): 
            email = data['email']
            additional_data = utils.additional_data_dictionary(
                data, self.fti
            )
            token = self.context.scheduler().reserve(
                email, (start, end), data=additional_data
            )
            
            if autoapprove:
                self.context.scheduler().approve_reservation(token)
                self.flash(_(u'Reservation successful'))
            else:
                self.flash(_(u'Added to waitinglist'))

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class GroupReservationForm(ResourceBaseForm, AllocationGroupView, ReservationSchemata):
    permission = 'zope2.View'

    grok.name('reserve-group')
    grok.require(permission)

    fields = field.Fields(IGroupReservation)
    label = _(u'Recurrance reservation')

    template = ViewPageTemplateFile('templates/reserve_group.pt')

    hidden_fields = ['group']
    ignore_requirements = True

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    def defaults(self, **kwargs):
        return dict(group=self.group)

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        sc = self.context.scheduler()
        autoapprove = not sc.allocations_by_group(data['group']).first().approve

        def reserve():
            email = data['email']
            additional_data = utils.additional_data_dictionary(
                data, self.fti
            )

            token = sc.reserve(email, group=data['group'], data=additional_data)

            if autoapprove:
                sc.approve_reservation(token)
                self.flash(_(u'Reservation successful'))
            else:
                self.flash(_(u'Added to waitinglist'))

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class ReservationDecisionForm(ResourceBaseForm, ReservationListView, ReservationUrls):
    
    grok.baseclass()

    fields = field.Fields(IApproveReservation)

    hidden_fields = ['reservation']
    ignore_requirements = True

    template = ViewPageTemplateFile('templates/decide_reservation.pt')

    show_links = False
    data = None

    @property
    def reservation(self):
        data = self.data
        return self.request.get('reservation', (data and data['reservation'] or None))

    def defaults(self):
        return dict(
            reservation=unicode(self.reservation)
        )

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class ReservationApprovalForm(ReservationDecisionForm):
    
    permission = 'cmf.ManagePortal'
    
    grok.name('approve-reservation')
    grok.require(permission)

    label = _(u'Approve reservation')

    @property
    def hint(self):
        if not self.pending_reservations():
            return _(u'No such reservation')

        return _(u'Do you really want to approve the following reservations?')

    @button.buttonAndHandler(_(u'Approve'))
    @extract_action_data
    def approve(self, data):

        self.data = data

        scheduler = self.scheduler
        def approve():
            scheduler.approve_reservation(data['reservation'])
            self.flash(_(u'Reservation confirmed'))

        utils.handle_action(action=approve, success=self.redirect_to_context)

class ReservationDenialForm(ReservationDecisionForm):

    permission = 'cmf.ManagePortal'
    
    grok.name('deny-reservation')
    grok.require(permission)

    label = _(u'Deny reservation')

    @property
    def hint(self):
        if not self.pending_reservations():
            return _(u'No such reservation')

        return _(u'Do you really want to deny the following reservations?')

    @button.buttonAndHandler(_(u'Deny'))
    @extract_action_data
    def deny(self, data):

        self.data = data

        scheduler = self.scheduler
        def deny():
            scheduler.deny_reservation(data['reservation'])
            self.flash(_(u'Reservation denied'))

        utils.handle_action(action=deny, success=self.redirect_to_context)

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
        if not self.approved_reservations():
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
        def delete():
            scheduler.remove_reservation(
                data['reservation'], data['start'], data['end']
            )
            self.flash(_(u'Reservation removed'))

        utils.handle_action(action=delete, success=self.redirect_to_context)

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