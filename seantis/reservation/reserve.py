# -*- coding: utf-8 -*-

import six

from logging import getLogger
log = getLogger('seantis.reservation')

from copy import copy
from DateTime import DateTime
from datetime import time, datetime
from five import grok
from isodate import parse_time
from plone.dexterity.interfaces import IDexterityFTI
from sqlalchemy.orm.exc import MultipleResultsFound
from z3c.form import button
from z3c.form import field
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.browser.radio import RadioFieldWidget
from zExceptions import NotFound
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryUtility
from zope.interface import Interface
from zope.schema import Choice, List, Set
from zope.security import checkPermission

from seantis.reservation import _
from seantis.reservation import db
from seantis.reservation.interfaces import (
    IGroupReservation,
    IReservation,
    IReservationEditTimeForm,
    IReservationTargetEmailForm,
    IReservationTargetForm,
    IResourceBase,
    IRevokeReservation,
    ISeantisReservationSpecific,
    ISelectionReservation,
)
from seantis.reservation import plone_session
from seantis.reservation import settings
from seantis.reservation import utils
from seantis.reservation.base import BaseView, BaseViewlet
from seantis.reservation.error import DirtyReadOnlySession, NoResultFound
from seantis.reservation.form import (
    AllocationGroupView,
    extract_action_data,
    ReservationListView,
    ResourceBaseForm,
)
from libres.db.models import Reservation
from seantis.reservation.overview import OverviewletManager
from seantis.reservation.restricted_eval import run_pre_reserve_script
from seantis.reservation.throttle import throttled


class ReservationUrls(object):
    """ Mixin class to create admin URLs for a specific reservation. """

    def revoke_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/revoke-reservation?token={}'.format(token)

    def approve_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/approve-reservation?token={}'.format(token)

    def deny_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/deny-reservation?token={}'.format(token)

    def update_all_url(self, token, context=None):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/update-reservation-data?token={}'.format(token)

    def print_all_url(self, token, context):
        context = context or self.context
        base = context.absolute_url()
        return base + u'/reservations?token={}&print=1'.format(token)

    def show_all_url(self, token, context):
        context = context or self.contex
        base = context.absolute_url()
        return base + u'/reservations?token={}'.format(token)


class ReservationSchemata(object):
    """ Mixin to use with plone.autoform and IResourceBase which makes the
    form it is used on display the formsets defined by the user.

    A formset is a Dexterity Type defined through the admin interface or
    code which has the behavior IReservationFormset.

    """

    @property
    def may_view_manager_sets(self):
        manager_permission = 'seantis.reservation.EditReservations'
        return checkPermission(manager_permission, self.context)

    def is_manager_set(self, fti):
        behavior = 'seantis.reservation.interfaces.IReservationManagerFormSet'
        return behavior in fti.behaviors

    @property
    def additionalSchemata(self):
        scs = []
        self.fti = dict()

        for ptype in self.context.formsets:
            fti = queryUtility(IDexterityFTI, name=ptype)
            if fti:
                if self.is_manager_set(fti) and not self.may_view_manager_sets:
                    continue  # do not show, but fill with defaults later

                schema = fti.lookupSchema()
                scs.append((ptype, fti.title, schema))

                self.fti[ptype] = (fti.title, schema)

        return scs


class SessionFormdataMixin(ReservationSchemata):

    def email(self, form_data=None):

        if not form_data or not form_data.get('email'):
            email = plone_session.get_email(self.context)
        else:
            email = form_data['email']
            plone_session.set_email(self.context, email)

        return email

    def merge_formdata(self, existing, new):

        for form in new:
            existing[form] = new[form]

        return existing

    @property
    def manager_ftis(self):
        ftis = {}

        for ptype in self.context.formsets:
            fti = queryUtility(IDexterityFTI, name=ptype)
            if fti and self.is_manager_set(fti):
                ftis[ptype] = (fti.title, fti.lookupSchema())

        return ftis

    def additional_data(self, form_data=None, add_manager_defaults=False):

        if not form_data:
            data = plone_session.get_additional_data(self.context)
        else:
            data = plone_session.get_additional_data(self.context) or dict()

            # merge the formdata for session use only, committing the
            # reservation only forms defined in the resource are
            # stored with the reservation to get proper separation
            data = self.merge_formdata(
                plone_session.get_additional_data(self.context) or dict(),
                utils.additional_data_dictionary(form_data, self.fti)
            )

            plone_session.set_additional_data(self.context, data)

        # the default values of manager forms are added to users without
        # the permission right before saving
        if add_manager_defaults and not self.may_view_manager_sets:
            defaults = {}
            manager_ftis = self.manager_ftis

            for key, info in manager_ftis.items():
                for name, f in field.Fields(info[1]).items():
                    if f.field.default is not None:
                        fieldkey = '{}.{}'.format(key, name)
                        defaults[fieldkey] = f.field.default

            data = self.merge_formdata(
                data, utils.additional_data_dictionary(defaults, manager_ftis)
            )

        # on the other hand, if the user is not allowed, the data is cleared,
        # just in case (really more of a dev-environment problem, but it
        # doesn't hurt anyway)
        if data:
            if not add_manager_defaults and not self.may_view_manager_sets:
                manager_ftis = self.manager_ftis

                for form in data.keys():
                    if form in manager_ftis:
                        del data[form]

        return data

    def session_id(self):
        return plone_session.get_session_id(self.context)


class YourReservationsData(object):
    """ Mixin providing functions to deal with 'your' reservations. """

    def reservations(self):
        """ Returns all reservations in the user's session """
        session_id = plone_session.get_session_id(self.context)

        reservations = db().reservations_by_session(session_id)
        reservations = reservations.order_by(
            Reservation.created, Reservation.token
        )

        return reservations.all()

    def resources(self):
        """ Returns a list of resources contained in the reservations. The
        result is a set of uuid strings (without hyphens).

        """
        return set(utils.string_uuid(r.resource) for r in self.reservations())

    @property
    def has_reservations(self):
        session_id = plone_session.get_session_id(self.context)
        return bool(db().reservations_by_session(session_id).first())

    def confirm_reservations(self, token=None):
        # Remove session_id from all reservations in the current session.
        db().confirm_reservations_for_session(
            plone_session.get_session_id(self.context),
            token
        )

    def remove_reservation(self, token):
        try:
            session_id = plone_session.get_session_id(self.context)
            db().remove_reservation_from_session(session_id, token)
        except NoResultFound:
            pass  # act idempotent to the user

    def redirect_to_your_reservations(self):
        self.request.response.redirect(
            self.context.absolute_url() + '/your-reservations'
        )


class ReservationBaseForm(ResourceBaseForm):

    def your_reservation_defaults(self, defaults):
        """ Extends the given dictionary containing field defaults with
        the defaults found in your-reservations.

        """

        default_email = self.email()
        if default_email:
            defaults['email'] = self.email()

        data = self.additional_data()

        if not data:
            return defaults

        for form in data:
            if form in self.context.formsets:
                for f in data[form]['values']:
                    defaults["%s.%s" % (form, f['key'])] = f['value']

        return defaults

    def run_reserve(
        self, data, approve_manually,
        start=None, end=None,
        group=None, quota=1,
        dates=None
    ):

        assert (start and end) or group or dates
        assert not (start and end and group and dates)

        email = self.email(data)
        additional_data = self.additional_data(data, add_manager_defaults=True)
        session_id = self.session_id()

        # only store forms defined in the formsets list
        if not self.context.formsets:
            additional_data = {}
        else:
            additional_data = dict(
                (
                    form, additional_data[form]
                ) for form in self.context.formsets if form in additional_data
            )

        run_pre_reserve_script(self.context, start, end, additional_data)

        def run():
            if start and end:
                return self.scheduler.reserve(
                    email, (start, end),
                    data=additional_data, session_id=session_id, quota=quota
                )
            elif group:
                return self.scheduler.reserve(
                    email, group=group,
                    data=additional_data, session_id=session_id, quota=quota
                )
            else:
                return self.scheduler.reserve(
                    email, dates,
                    data=additional_data, session_id=session_id, quota=quota
                )

        token = throttled(run, 'reserve')()

        if not approve_manually:
            self.scheduler.approve_reservations(token)

        self.flash(
            _(
                u'Added reservation to your list. '
                u'You have 15 minutes to confirm your reservations.'
            )
        )


class ReservationForm(
        ReservationBaseForm,
        SessionFormdataMixin,
        YourReservationsData
):

    permission = 'seantis.reservation.SubmitReservation'

    grok.name('reserve')
    grok.require(permission)

    context_buttons = ('reserve', )
    standalone_buttons = ('cancel', )

    fields = field.Fields(IReservation)
    label = _(u'Resource reservation')

    fti = None

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    @property
    def css_class(self):
        return super(ReservationForm, self).css_class + ' next-next-wizard'

    @property
    def hidden_fields(self):
        hidden = ['id']

        try:
            allocation = self.allocation(self.id)

            if allocation:

                if allocation.quota_limit == 1:
                    hidden.append('quota')

                if allocation.whole_day:
                    if not allocation.partly_available:
                        hidden.append('start_time')
                        hidden.append('end_time')

        except DirtyReadOnlySession:
            pass

        except NotFound:
            pass

        return hidden

    @property
    def disabled_fields(self):
        disabled = ['day']
        try:
            allocation = self.allocation(self.id)

            if allocation:

                if not allocation.partly_available:
                    disabled.append('start_time')
                    disabled.append('end_time')

        except DirtyReadOnlySession:
            pass

        except NotFound:
            pass

        return disabled

    def defaults(self, **kwargs):
        defaults = self.your_reservation_defaults(dict(id=self.id))
        self.inject_missing_data(defaults)

        return defaults

    def allocation(self, id):
        if not id:
            raise NotFound

        try:
            return self.scheduler.allocation_by_id(id)
        except NoResultFound:
            raise NotFound

    def strptime(self, value):
        if not value:
            return None

        if not isinstance(value, six.string_types):
            return value

        dt = DateTime(value)
        return time(dt.hour(), dt.minute())

    def validate(self, data):
        try:
            start, end = utils.get_date_range(
                data['day'], data['start_time'], data['end_time']
            )
            if not self.allocation(data['id']).contains(start, end):
                utils.form_error(_(u'Reservation out of bounds'))

            return start, end
        except (NoResultFound, TypeError):
            utils.form_error(_(u'Invalid reservation request'))

    def inject_missing_data(self, data, allocation=None):
        """ Adds the date and start-/end-time to the data if they are missing,
        which happens because those fields may be disabled and therefore are
        not transferred when submitting the form.

        The fields are injected into the passed dictionary, which may be
        the reservations defaults or the submitted form data.

        """
        extracted, errors = self.extractData(setErrors=False)

        # the extracted fields may contain field values which need to be
        # injected so the defaults are filled - otherwise no value is updated
        # on the disabled field
        for f in ('day', 'start_time', 'end_time'):
            if extracted.get(f) is not None:
                data[f] = extracted[f]

        # if the extracted data was not of any help the id of the allocation
        # is our last resort.
        try:
            allocation = allocation or self.allocation(data['id'])
        except DirtyReadOnlySession:
            return

        tz = settings.timezone()

        if data.get('day') is None:
            data['day'] = allocation.display_start(tz).date()

        if data.get('start_time') is None:
            data['start_time'] = allocation.display_start(tz).time()

        if data.get('end_time') is None:
            data['end_time'] = allocation.display_end(tz).time()

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        allocation = self.allocation(data['id'])
        approve_manually = allocation.approve_manually

        self.inject_missing_data(data, allocation)

        start, end = self.validate(data)
        quota = int(data.get('quota', 1))

        # whole day allocations don't show the start / end time which is to
        # say the data arrives with 00:00 - 00:00. we align that to the day
        if allocation.whole_day:

            if not allocation.partly_available:
                assert start == end

            if start == end:
                start, end = utils.align_range_to_day(start, end)

        def reserve():
            self.run_reserve(
                data=data, approve_manually=approve_manually,
                start=start, end=end, quota=quota
            )

        utils.handle_action(
            action=reserve, success=self.redirect_to_your_reservations
        )

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def customize_fields(self, fields):
        """ This function is called by ResourceBaseForm every time fields are
        created from the schema by z3c. This allows for changes before the
        fields are properly integrated into the form.

        Here, we want to make sure that all formset schemas have sane widgets.

        """

        for f in fields.values():

            field_type = type(f.field)

            if field_type is List or field_type is Set:
                f.widgetFactory = CheckBoxFieldWidget

            elif field_type is Choice:
                f.widgetFactory = RadioFieldWidget


class GroupReservationForm(
        ReservationForm,
        AllocationGroupView,
        SessionFormdataMixin,
        YourReservationsData
):
    permission = 'seantis.reservation.SubmitReservation'

    grok.name('reserve-group')
    grok.require(permission)

    context_buttons = ('reserve', )
    standalone_buttons = ('cancel', )

    fields = field.Fields(IGroupReservation)
    label = _(u'Recurrance reservation')

    template = ViewPageTemplateFile('templates/reserve_group.pt')

    ignore_requirements = True

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    @property
    def hidden_fields(self):
        hidden = ['group']

        try:
            allocation = self.group and self.scheduler.allocations_by_group(
                self.group
            ).first()

            if allocation.quota_limit == 1:
                hidden.append('quota')

        except DirtyReadOnlySession:
            pass

        return hidden

    def defaults(self, **kwargs):
        return self.your_reservation_defaults(dict(group=self.group, quota=1))

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):

        approve_manually = self.scheduler.allocations_by_group(data['group']) \
            .first().approve_manually

        def reserve():
            self.run_reserve(
                data=data, approve_manually=approve_manually,
                group=data['group'], quota=data['quota']
            )

        utils.handle_action(
            action=reserve, success=self.redirect_to_your_reservations
        )

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class SelectionReservationForm(
        ReservationForm,
        AllocationGroupView,
        SessionFormdataMixin,
        YourReservationsData
):
    permission = 'seantis.reservation.SubmitReservation'

    grok.name('reserve-selection')
    grok.require(permission)

    context_buttons = ('reserve', )
    standalone_buttons = ('cancel', )

    fields = field.Fields(ISelectionReservation)
    label = _(u'Reserve selected')

    template = ViewPageTemplateFile('templates/reserve_selection.pt')

    ignore_requirements = True

    autoGroups = True
    enable_form_tabbing = True
    default_fieldset_label = _(u'General Information')

    hidden_fields = ['ids', 'start_time', 'end_time']

    @property
    def start_time(self):
        if self.request.get('start_time'):
            return parse_time(self.request.get('start_time'))
        else:
            return None

    @property
    def end_time(self):
        if self.request.get('end_time'):
            return parse_time(self.request.get('end_time'))
        else:
            return None

    @property
    def quota(self):
        try:
            return int(self.request.get('quota', 0))
        except (TypeError, ValueError):
            return None

    @property
    def ids(self):
        ids = (
            self.request.get('allocation_id')
            or
            self.request.get('form.widgets.ids')
        )

        if not ids:
            return tuple()

        if isinstance(ids, six.string_types):
            ids = ids.split(',')

        return ids

    def defaults(self, **kwargs):
        defaults = {
            'ids': ','.join(self.ids)
        }

        s, e = self.start_time, self.end_time

        if s or e and not utils.whole_day(s, e):
            defaults['start_time'] = s
            defaults['end_time'] = e

        if self.quota:
            defaults['quota'] = self.quota

        return self.your_reservation_defaults(defaults)

    def allocations(self):
        return self.scheduler.allocations_by_ids(self.ids).all()

    @button.buttonAndHandler(_(u'Reserve'))
    @extract_action_data
    def reserve(self, data):
        approve_manually = self.scheduler.manual_approval_required(self.ids)

        def reserve():
            dates = list(self.scheduler.allocation_dates_by_ids(
                self.ids, data['start_time'], data['end_time']
            ))
            self.run_reserve(
                data=data, approve_manually=approve_manually,
                dates=dates,
                quota=data['quota']
            )

        utils.handle_action(
            action=reserve, success=self.redirect_to_your_reservations
        )

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context(view='search')


class YourReservations(ResourceBaseForm, YourReservationsData):

    permission = "seantis.reservation.SubmitReservation"

    grok.name('your-reservations')
    grok.require(permission)

    context_buttons = ('finish', )
    standalone_buttons = ('cancel', )

    grok.context(Interface)

    css_class = 'seantis-reservation-form'

    template = grok.PageTemplateFile('templates/your_reservations.pt')

    @button.buttonAndHandler(_(u'Submit Reservations'), name="finish")
    def finish(self, data):

        resources = self.resources()

        def on_success():
            self.request.response.redirect(
                '{context}/thank-you-for-reserving?uuid={uuids}'.format(
                    context=self.context.absolute_url(),
                    uuids='&uuid='.join(resources)
                )
            )

        utils.handle_action(self.confirm_reservations, success=on_success)

    # the button's name is 'cancel' because it should behave like a cancel
    # button in the browser (namely, it should not refetch the events)
    @button.buttonAndHandler(_(u'Reserve More'), name="cancel")
    def proceed(self, data):
        # Don't do anything, reservations stay in the session.
        self.request.response.redirect(self.context.absolute_url())

    def update(self):
        if 'remove' in self.request and utils.is_uuid(self.request['remove']):
            self.remove_reservation(self.request['remove'])

            self.request.response.redirect(self.context.absolute_url())

        super(YourReservations, self).update()


class YourReservationsViewlet(BaseViewlet, YourReservationsData):
    grok.context(Interface)
    grok.name('seantis.reservation.YourReservationsviewlet')
    grok.require('zope2.View')
    grok.viewletmanager(OverviewletManager)

    grok.order(0)

    template = grok.PageTemplateFile('templates/your_reservations_viewlet.pt')

    def available(self):
        return self.has_reservations

    def finish_url(self):
        return self.context.absolute_url() + '/your-reservations'


class ReservationTargetForm(ResourceBaseForm):
    """ Describes a form with a hidden reservation field and the ability to
    set the reservation using a query parameter:

    example-form?token=298c6de470f94c64928c14246f3ee9e5

    Optionally, an id can be given to select a specific reservation out
    of many possible reservations belonging to one token:

    example-form?token=298c6de470f94c64928c14246f3ee9e5&id=123

    """

    grok.baseclass()
    fields = field.Fields(IReservationTargetForm)
    hidden_fields = ('token', 'id')
    extracted_data = {}

    @property
    def token(self):
        return self.request.get(
            'token', self.extracted_data.get('token')
        )

    @property
    def id(self):
        id = self.request.get(
            'id', self.extracted_data.get('id')
        )
        return int(id) if id else None

    def defaults(self):
        return dict(token=self.token, id=self.id)


class ReservationDecisionForm(
    ReservationTargetForm,
    ReservationListView,
    ReservationUrls
):
    """ Base class for admin's approval / denial forms. """

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)

    template = ViewPageTemplateFile('templates/decide_reservation.pt')

    show_links = False


class ReservationApprovalForm(ReservationDecisionForm):

    permission = 'seantis.reservation.ApproveReservations'

    grok.name('approve-reservation')
    grok.require(permission)

    context_buttons = ('approve', )
    standalone_buttons = ('cancel', )

    label = _(u'Approve reservation')

    @property
    def hint(self):
        if not self.pending_reservations():
            return _(u'No such reservation')

        return _(u'Do you really want to approve the following reservations?')

    @button.buttonAndHandler(_(u'Approve'))
    @extract_action_data
    def approve(self, data):

        def approve():
            self.scheduler.approve_reservations(data['token'])
            self.flash(_(u'Reservation approved'))

        utils.handle_action(action=approve, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationDenialForm(ReservationDecisionForm):

    permission = 'seantis.reservation.ApproveReservations'

    grok.name('deny-reservation')
    grok.require(permission)

    destructive_buttons = ('deny', )
    standalone_buttons = ('cancel', )

    label = _(u'Deny reservation')

    @property
    def hint(self):
        if not self.pending_reservations():
            return _(u'No such reservation')

        return _(u'Do you really want to deny the following reservations?')

    @button.buttonAndHandler(_(u'Deny'))
    @extract_action_data
    def deny(self, data):

        def deny():
            self.scheduler.deny_reservation(data['token'])
            self.flash(_(u'Reservation denied'))

        utils.handle_action(action=deny, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationRevocationForm(
    ReservationTargetForm,
    ReservationListView,
    ReservationUrls
):

    permission = 'seantis.reservation.ApproveReservations'

    grok.name('revoke-reservation')
    grok.require(permission)
    grok.layer(ISeantisReservationSpecific)

    destructive_buttons = ('revoke', )
    standalone_buttons = ('cancel', )

    fields = field.Fields(IRevokeReservation)
    template = ViewPageTemplateFile('templates/revoke_reservation.pt')

    label = _(u'Revoke reservation')

    show_links = False

    @property
    def hint(self):
        if not self.has_reservations:
            return _(u'No such reservation')

        return _(
            u'Do you really want to revoke the following reservations?'
        )

    @property
    def has_reservations(self):
        return self.approved_reservations() and True or False

    @button.buttonAndHandler(_(u'Revoke'))
    @extract_action_data
    def revoke(self, data):

        # might happen if the user submits twice
        if not self.has_reservations:
            return

        def revoke():
            self.scheduler.revoke_reservation(
                token=data['token'],
                reason=data['reason'],
                id=data.get('id'),
                send_email=data['send_email']
            )
            self.flash(_(u'Reservation revoked'))

        utils.handle_action(action=revoke, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationList(BaseView, ReservationListView, ReservationUrls):

    permission = "seantis.reservation.ViewReservations"

    grok.name('reservations')
    grok.require(permission)

    grok.context(IResourceBase)

    template = grok.PageTemplateFile('templates/reservations.pt')

    @property
    def group(self):
        if 'group' in self.request:
            return six.text_type(self.request['group'].decode('utf-8'))
        else:
            return u''

    @property
    def token(self):
        """ Limits the list to the given reservation. """
        return self.request.get('token', None)

    @property
    def print_site(self):
        """ Returns true if the document should be printed when opening it. """
        return self.request.get('print', None) is not None

    @property
    def body_classes(self):
        if utils.is_uuid(self.reservation):
            return ['single-reservation-view']


class ReservationEditTimeForm(ReservationTargetForm):

    permission = 'seantis.reservation.EditReservations'

    grok.name('change-reservation')
    grok.require(permission)
    grok.layer(ISeantisReservationSpecific)

    destructive_buttons = ('save', )
    standalone_buttons = ('cancel', )

    fields = field.Fields(IReservationEditTimeForm).select(
        'token', 'id', 'start_time', 'end_time', 'send_email', 'reason'
    )

    @property
    def label(self):
        if self.reservation:
            return _(u'Change reservation')
        else:
            return _(u'This reservation cannot be changed')

    @utils.cached_property
    def reservation(self):
        if not (self.token and self.id):
            return None

        try:
            reservation = self.scheduler.reservations_by_token(
                self.token, self.id
            ).one()
        except MultipleResultsFound:
            return None

        if reservation.target_type != 'allocation':
            return None

        allocation = self.scheduler.allocations_by_reservation(
            self.token, self.id
        ).one()

        if not allocation.partly_available:
            return None

        return reservation

    def defaults(self):
        parent = super(ReservationEditTimeForm, self).defaults()

        if self.reservation:
            tz = settings.timezone()

            parent.update({
                'start_time': self.reservation.display_start(tz).time(),
                'end_time': self.reservation.display_end(tz).time()
            })

        return parent

    @button.buttonAndHandler(_(u'Save'))
    @extract_action_data
    def save(self, data):

        # might happen if the user submits twice
        if not self.reservation:
            return

        def change():
            start = datetime.combine(
                self.reservation.start.date(), data['start_time']
            )
            end = datetime.combine(
                self.reservation.end.date(), data['end_time']
            )

            changed = self.scheduler.change_reservation_time(
                token=data['token'],
                id=data['id'],
                new_start=start,
                new_end=end,
                send_email=data['send_email'],
                reason=data['reason']
            )
            if changed:
                self.flash(_(u'Reservation changed.'))
            else:
                self.flash(_(u'There was nothing to change.'))

        utils.handle_action(action=change, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class ReservationDataEditForm(ReservationTargetForm, ReservationSchemata):

    permission = "seantis.reservation.EditReservations"

    grok.name('update-reservation-data')
    grok.require(permission)

    grok.context(IResourceBase)
    grok.layer(ISeantisReservationSpecific)

    fields = field.Fields(IReservationTargetEmailForm)

    context_buttons = ('save', )
    standalone_buttons = ('cancel', )
    extracted_errors = []

    label = _(u'Edit Formdata')
    default_fieldset_label = _(u'Reservation')

    template = ViewPageTemplateFile('templates/form.pt')

    @property
    def broken_data(self):
        return self.broken

    @utils.cached_property
    def reservation(self):
        if not self.token:
            return None
        try:
            return self.scheduler.reservations_by_token(self.token).first()
        except DirtyReadOnlySession:
            return None

    @utils.cached_property
    def reservation_data(self):
        return (self.reservation and self.reservation.data or {})

    def separate_broken_data(self):
        """ Goes through the reservation data and returns the the reservation
        data in two pieces. The first is the working data, the second is the
        broken data.

        Broken data is the data which cannot be loaded in the form, because
        the underlying form schema has changed since the data has been
        written.

        """
        def init_form(data, form):
            if form in data:
                return data

            data[form] = copy(self.reservation_data[form])
            data[form]['values'] = []

            return data

        working, broken = {}, {}

        for form in self.reservation_data:
            for value in self.reservation_data[form]['values']:
                id = '.'.join((form, value['key']))

                if self.get_field(id) and self.get_field(id):
                    init_form(working, form)[form]['values'].append(value)
                else:
                    init_form(broken, form)[form]['values'].append(value)

        return working, broken

    def defaults(self):
        defaults = super(ReservationDataEditForm, self).defaults()

        if not self.reservation:
            return defaults

        defaults['email'] = self.reservation.email

        self.working, self.broken = self.separate_broken_data()

        data = self.working

        errors = [e.widget.__name__ for e in self.extracted_errors]

        for form in data:

            for value in data[form]['values']:
                if isinstance(value['value'], six.string_types):
                    decoded = utils.userformdata_decode(value['value'])
                    fieldvalue = decoded or value['value']
                else:
                    fieldvalue = value['value']

                fieldkey = '{}.{}'.format(form, value['key'])
                if fieldkey in self.extracted_data or fieldkey in errors:
                    continue
                else:
                    defaults[fieldkey] = fieldvalue

        return defaults

    def customize_fields(self, fields):

        for f in fields.values():

            field_type = type(f.field)

            if field_type is List or field_type is Set:
                f.widgetFactory = CheckBoxFieldWidget

            elif field_type is Choice:
                f.widgetFactory = RadioFieldWidget

    @button.buttonAndHandler(_(u'Save'))
    @extract_action_data
    def save(self, data):

        broken = self.separate_broken_data()[1]
        working = utils.additional_data_dictionary(data, self.fti)

        if broken:
            self.additional_data = utils.merge_data_dictionaries(
                broken, working
            )
        else:
            self.additional_data = working

        def save():
            if self.reservation.email != data['email']:
                self.scheduler.change_email(self.token, data['email'])

            self.scheduler.change_reservation_data(
                self.token, self.additional_data
            )
            self.flash(_(u'Formdata updated'))

        utils.handle_action(
            action=save, success=self.redirect_to_context
        )

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()
