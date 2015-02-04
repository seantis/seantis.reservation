import logging
logger = logging.getLogger('seantis.reservation')

import pytz

from zope import schema
from zope.interface import Interface, Invalid, invariant
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from z3c.form.browser.radio import RadioFieldWidget

from plone import api
from plone.directives import form
from plone.z3cform import layout
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper

from Products.Five.browser.pagetemplatefile import ZopeTwoPageTemplateFile

from seantis.plonetools.schemafields import validate_email

from seantis.reservation import _
from seantis.reservation.restricted_eval import validate_expression


def valid_expression(expression):
    try:
        validate_expression(expression, mode='exec')
    except Exception as e:
        raise Invalid(str(e))
    return True


class ISeantisReservationSettings(Interface):

    throttle_minutes = schema.Int(
        title=_(u"Reservation Throttling"),
        description=_(
            u'The number of minutes a user needs to wait between '
            u'reservations, use 0 if no throttling should occur. '
            u'Users with the \'Unthrottled Reservations\' permission '
            u'are excempt from this rule (Reservation-Managers and '
            u'Reservation-Assistants by default).'
        )
    )

    form.widget(send_email_to_managers=RadioFieldWidget)
    send_email_to_managers = schema.Choice(
        title=_(u"Email Notifications for Managers"),
        description=_(
            u'Either send an email to the manager(s) responsible for the '
            u'resource or use a single recipient address for all resources.'
        ),
        source=SimpleVocabulary(
            [
                SimpleTerm(
                    value='never',
                    title=_(u'Do not send manager emails')
                ),
                SimpleTerm(
                    value='by_path',
                    title=_(u'Send to the responsible manager(s)')
                ),
                SimpleTerm(
                    value='by_address',
                    title=_(u'Always send to the following address:')
                )
            ]
        ),
        default='by_path'
    )

    # XXX
    # the plone registry is a bit weird in how it handles fields, it will
    # not work with seantis.plonetools' Email field - so we use TextLine with
    # a valid_email constraint.
    manager_email = schema.TextLine(
        title=_(u"Email Address for Manager Emails"),
        required=False,
        default=u'',
        constraint=validate_email
    )

    send_email_to_reservees = schema.Bool(
        title=_(u"Email Notifications for Reservees"),
        description=_(
            u'Send emails about made, approved and denied reservations '
            u'to the user that made the reservation.'
        )
    )

    pre_reservation_script = schema.Text(
        title=_(u"Pre-Reservation Script"),
        description=_(
            u'Run custom validation code for reservations. This is for '
            u'advanced users only and may disable the reservations process. '
            u'For documentation study the source code at Github.'
        ),
        required=False,
        constraint=valid_expression
    )

    available_threshold = schema.Int(
        title=_(u'Available Threshold (%)'),
        description=_(
            u'Allocations with an availability above or equal to this value '
            u'are considered available and are shown green'
        ),
        default=75
    )

    partly_available_threshold = schema.Int(
        title=_(u'Partly Available Threshold (%)'),
        description=_(
            u'Allocations with an availability above or equal to this value '
            u'but below the available threshold are considered partly '
            u'available and are shown orange. Allocations with an '
            u'availability below this value are considered unavailable and '
            u'are shown red'
        ),
        default=1
    )

    @invariant
    def isValidThreshold(Allocation):

        thresholds = [
            Allocation.available_threshold,
            Allocation.partly_available_threshold,
        ]

        if thresholds[0] == thresholds[1]:
            raise Invalid(
                _(u'Thresholds must have differing values')
            )

        if not (thresholds[0] > thresholds[1]):
            raise Invalid(
                _(
                    u'The available threshold must have a larger value than '
                    u'the partly available threshold'
                )
            )

        for threshold in thresholds:
            if not (0 <= threshold and threshold <= 100):
                raise Invalid(
                    _(
                        u'Thresholds must have values between 0 and 100'
                    )
                )

    @invariant
    def filled_manager_email(settings):
        if settings.send_email_to_managers == 'by_address':
            if not (settings.manager_email or u'').strip():
                raise Invalid(_(
                    u'Please specify an address to send the manager emails to'
                ))


def get(name):
    prefix = ISeantisReservationSettings.__identifier__
    return api.portal.get_registry_record('.'.join((prefix, name)))


def set(name, value):
    prefix = ISeantisReservationSettings.__identifier__
    return api.portal.set_registry_record('.'.join((prefix, name)), value)


def timezone():
    return pytz.timezone('UTC')


class SeantisReservationSettingsPanelForm(RegistryEditForm):
    schema = ISeantisReservationSettings
    label = _(u"Seantis Reservation Control Panel")

    template = ZopeTwoPageTemplateFile('templates/controlpanel.pt')


SeantisReservationControlPanelView = layout.wrap_form(
    SeantisReservationSettingsPanelForm, ControlPanelFormWrapper
)
