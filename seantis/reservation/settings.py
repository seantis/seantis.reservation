import logging
logger = logging.getLogger('seantis.reservation')

from zope import schema
from zope.interface import Interface
from zope.component import getUtility

from plone.z3cform import layout
from plone.registry.interfaces import IRegistry
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper

from Products.Five.browser.pagetemplatefile import ZopeTwoPageTemplateFile

from seantis.reservation import _


class ISeantisReservationSettings(Interface):

    throttle_minutes = schema.Int(
        title=_(u"Reservation Throttling"),
        description=_(
            u'The number of minutes a user needs to wait between '
            u'reservations, use 0 if no throttling should occur. '
            u'Users with the \'Unthrottled Reservations\' permission '
            u'are excempt from this rule (Reservation-Managers by default).'
        )
    )

    send_email_to_managers = schema.Bool(
        title=_(u"Email Notifications for Managers"),
        description=_(
            u'Send emails about newly made reservations to '
            u'the first reservation managers found in the path.'
        )
    )

    send_approval_email_to_managers = schema.Bool(
        title=_(u"Approval Email Notifications for Managers"),
        description=_(
            u'Send emails about new pending reservations to '
            u'the first reservation managers found in the path.'
        )
    )

    send_email_to_reservees = schema.Bool(
        title=_(u"Email Notifications for Reservees"),
        description=_(
            u'Send emails about made, approved and denied reservations '
            u'to the user that made the reservation.'
        )
    )


def get(name, default=None):
    registry = getUtility(IRegistry)
    settings = registry.forInterface(ISeantisReservationSettings)

    assert hasattr(settings, name), "Unknown setting: %s" % name
    return getattr(settings, name)


class SeantisReservationSettingsPanelForm(RegistryEditForm):
    schema = ISeantisReservationSettings
    label = _(u"Seantis Reservation Control Panel")

    template = ZopeTwoPageTemplateFile('templates/controlpanel.pt')


SeantisReservationControlPanelView = layout.wrap_form(
    SeantisReservationSettingsPanelForm, ControlPanelFormWrapper
)
