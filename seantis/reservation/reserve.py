from datetime import date, time, timedelta
from DateTime import DateTime
from five import grok

from plone.app.uuid.utils import uuidToObject
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import queryUtility
from plone.directives import form
from zope.interface import Interface

from z3c.form import field
from z3c.form import button
from z3c.form.browser.radio import RadioFieldWidget
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.schema import Choice, List

from seantis.reservation.throttle import throttled
from seantis.reservation.interfaces import (
    IResourceBase,
    IReservation,
    IGroupReservation,
    IRemoveReservation,
    IApproveReservation,
)
from seantis.reservation.models import Reservation
from seantis.reservation.error import DirtyReadOnlySession
from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation import plone_session
from seantis.reservation import Session
from seantis.reservation.session import serialized
from seantis.reservation.form import (
    ResourceBaseForm,
    AllocationGroupView,
    ReservationListView,
    extract_action_data
)

from seantis.reservation.overview import OverviewletManager
from seantis.reservation.error import NoResultFound


class ReservationUrls(object):
    """ Mixin class to create admin URLs for a specific reservation. """

    def remove_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/remove-reservation?reservation=%s' % token

    def approve_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/approve-reservation?reservation=%s' % token

    def deny_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/deny-reservation?reservation=%s' % token


class ReservationSchemata(object):
    """ Mixin to use with plone.autoform and IResourceBase which makes the
    form it is used on display the formsets defined by the user.

    A formset is a Dexterity Type defined through the admin interface or
    code which has the behavior IReservationFormset.

    """

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

    def email(self, form_data=None):
        email = plone_session.get_email(self.context)
        if email is None and form_data is not None:
            email = form_data['email']
            plone_session.set_email(self.context, email)
        return email

    def additional_data(self, form_data=None):
        additional_data = plone_session.get_additional_data(self.context)
        if additional_data is None and form_data is not None:
            additional_data = utils.additional_data_dictionary(
                form_data, self.fti
            )
            plone_session.set_additional_data(
                self.context, additional_data
            )
        return additional_data

    def session_id(self):
        return plone_session.get_session_id(self.context)


class ReservationForm(ResourceBaseForm, ReservationSchemata):
    permission = 'seantis.reservation.SubmitReservation'

    grok.name('reserve')
    grok.require(permission)

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    fti = None

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    @property
    def disabled_fields(self):
        disabled = ['day']
        try:
            if self.id and not self.allocation(self.id).partly_available:
                disabled = ['day', 'start_time', 'end_time']
        except DirtyReadOnlySession:
            pass

        return disabled

    def updateFields(self):
        self.form.groups = []
        if self.email() is not None:
            self.fields = self.fields.omit('email')

        if self.additional_data() is not None:
            return

        ResourceBaseForm.updateFields(self)

    def defaults(self, **kwargs):
        return dict(id=self.id)

    def allocation(self, id):
        return self.scheduler.allocation_by_id(id)

    def strptime(self, value):
        if not value:
            return None

        if not isinstance(value, basestring):
            return value

        dt = DateTime(value)
        return time(dt.hour(), dt.minute())

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

    def redirect_to_my_reservations(self):
        self.request.response.redirect(self.context.absolute_url() + '/my_reservations')

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        start, end = self.validate(data)
        autoapprove = not self.allocation(data['id']).approve

        def reserve():

            email = self.email(data)
            additional_data = self.additional_data(data)
            session_id = self.session_id()

            token = self.scheduler.reserve(
                email, (start, end), data=additional_data,
                session_id=session_id
            )

            if autoapprove:
                self.scheduler.approve_reservation(token)
                self.flash(_(u'Reservation successful'))
            else:
                self.flash(_(u'Added to waitinglist'))

        action = throttled(reserve, self.context, 'reserve')
        utils.handle_action(action=action, success=self.redirect_to_my_reservations)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def customize_fields(self, fields):
        """ This function is called by ResourceBaseForm every time fields are
        created from the schema by z3c. This allows for changes before the
        fields are properly integrated into the form.

        Here, we want to make sure that all formset schemas have sane widgets.

        """

        for field in fields.values():

            field_type = type(field.field)

            if field_type is List:
                field.widgetFactory = CheckBoxFieldWidget

            elif field_type is Choice:
                field.widgetFactory = RadioFieldWidget

    def updateActions(self):
        """ Ensure that the 'Reserve' Button has the context css class. """
        super(ReservationForm, self).updateActions()
        self.actions['reserve'].addClass("context")


class GroupReservationForm(ResourceBaseForm, AllocationGroupView,
                           ReservationSchemata):
    permission = 'seantis.reservation.SubmitReservation'

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

        sc = self.scheduler
        autoapprove = not sc.allocations_by_group(data['group']) \
            .first().approve

        def reserve():
            email = self.email(data)
            additional_data = self.additional_data(data)
            session_id = self.session_id()

            token = sc.reserve(
                email, group=data['group'], data=additional_data,
                session_id=session_id,
            )

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


class MyReservationsData(object):

    def display_date(self, start, end):
        """ Formates the date range given for display. """
        end += timedelta(microseconds=1)
        if start.date() == end.date():
            return start.strftime('%d.%m.%Y %H:%M - ') + end.strftime('%H:%M')
        else:
            return start.strftime('%d.%m.%Y %H:%M - ') \
                + end.strftime('%d.%m.%Y %H:%M')

    def reservations(self):
        """ Returns all reservations in the user's session """
        session_id = plone_session.get_session_id(self.context)
        query = Session.query(Reservation)
        query = query.filter(Reservation.session_id == session_id)
        return query.all()

    def reservation_data(self):
        """ Prepares data to be shown in the my reservation's table """
        reservations = []
        for reservation in self.reservations():
            resource_uid = str(reservation.resource).replace('-', '')
            resource = uuidToObject(resource_uid)
            if resource is not None:
                data = {}
                data['title'] = utils.get_resource_title(resource)
                # TODO: Multiple timespans?
                start, end = reservation.timespans()[0]
                data['time'] = self.display_date(start, end)
                reservations.append(data)

        return reservations


class MyReservations(form.Form, MyReservationsData):

    permission = "seantis.reservation.SubmitReservation"

    grok.name('my_reservations')
    grok.require(permission)

    grok.context(Interface)

    css_class = 'seantis-reservation-form'

    template = grok.PageTemplateFile('templates/my_reservations.pt')

    @button.buttonAndHandler(_(u'finish'))
    @serialized
    def finish(self, data):
        # Remove session_id from all reservations in the current session.
        for reservation in self.reservations():
            reservation.session_id = None
        self.request.response.redirect(self.context.absolute_url())

    @button.buttonAndHandler(_(u'proceed'))
    def proceed(self, data):
        # Don't do anything, reservations stay in the session.
        self.request.response.redirect(self.context.absolute_url())


class MyReservationsViewlet(grok.Viewlet, MyReservationsData):
    grok.context(Interface)
    grok.name('seantis.reservation.myreservationsviewlet')
    grok.require('zope2.View')
    grok.viewletmanager(OverviewletManager)

    grok.order(0)

    template = grok.PageTemplateFile('templates/my_reservations_viewlet.pt')

    def available(self):
        return self.reservations() != []

    def finish_url(self):
        return self.context.absolute_url() + '/my_reservations'


class ReservationDecisionForm(ResourceBaseForm, ReservationListView,
                              ReservationUrls):
    """ Base class for admin's approval / denial forms. """

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
        return self.request.get(
            'reservation', (data and data['reservation'] or None)
        )

    def defaults(self):
        return dict(
            reservation=unicode(self.reservation)
        )


class ReservationApprovalForm(ReservationDecisionForm):

    permission = 'seantis.reservation.ApproveReservations'

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

        def approve():
            self.scheduler.approve_reservation(data['reservation'])
            self.flash(_(u'Reservation confirmed'))

        utils.handle_action(action=approve, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationDenialForm(ReservationDecisionForm):

    permission = 'seantis.reservation.ApproveReservations'

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

        def deny():
            self.scheduler.deny_reservation(data['reservation'])
            self.flash(_(u'Reservation denied'))

        utils.handle_action(action=deny, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationRemoveForm(ResourceBaseForm, ReservationListView,
                            ReservationUrls):

    permission = 'seantis.reservation.ApproveReservations'

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
            return _(
                u'Do you really want to remove the following reservations?'
            )

        if self.reservation and all((self.start, self.end)):
            return _(u'Do you really want to remove '
                     u'the following timespans from the reservation?')

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):

        def delete():
            self.scheduler.remove_reservation(
                data['reservation'], data['start'], data['end']
            )
            self.flash(_(u'Reservation removed'))

        utils.handle_action(action=delete, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationList(grok.View, ReservationListView, ReservationUrls):

    permission = "seantis.reservation.ViewReservations"

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
