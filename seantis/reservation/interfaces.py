from dateutil import rrule

from five import grok

from zope import schema
from zope.interface import Interface, invariant, Invalid, Attribute
from zope.component import getAllUtilitiesRegisteredFor as getallutils
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from Products.CMFDefault.utils import checkEmailAddress
from Products.CMFDefault.exceptions import EmailAddressInvalid

from plone.directives import form
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import schemaNameToPortalType as getname

from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form import widget
from seantis.reservation import _, utils
from seantis.reservation.raster import VALID_RASTER_VALUES

from seantis.reservation.mail_templates import templates

from seantis.reservation.utils import _languagelist

days = SimpleVocabulary(
    [
        SimpleTerm(value=rrule.MO, title=_(u'Mo')),
        SimpleTerm(value=rrule.TU, title=_(u'Tu')),
        SimpleTerm(value=rrule.WE, title=_(u'We')),
        SimpleTerm(value=rrule.TH, title=_(u'Th')),
        SimpleTerm(value=rrule.FR, title=_(u'Fr')),
        SimpleTerm(value=rrule.SA, title=_(u'Sa')),
        SimpleTerm(value=rrule.SU, title=_(u'Su')),
    ]
)

recurrence = SimpleVocabulary(
    [
        SimpleTerm(value=False, title=_(u'Once')),
        SimpleTerm(value=True, title=_(u'Daily')),
    ]
)


@grok.provider(IContextSourceBinder)
def form_interfaces(context):
    """ Used as a source for a vocabulary this function returns a vocabulary
    of interfaces which may be used as sub-forms in a resource object.

    """
    dutils = getallutils(IDexterityFTI)
    behavior = 'seantis.reservation.interfaces.IReservationFormSet'
    interfaces = [
        (u.title, u.lookupSchema()) for u in dutils if behavior in u.behaviors
    ]

    def get_term(item):
        return SimpleTerm(title=item[0], value=getname(item[1].__name__))

    return SimpleVocabulary(map(get_term, interfaces))


@grok.provider(IContextSourceBinder)
def plone_languages(context):
    def get_term(item):
        return SimpleTerm(title=item[1]['native'], value=item[0])

    terms = sorted(map(get_term, _languagelist.items()), key=lambda t: t.title)

    return SimpleVocabulary(terms)


# TODO -> Move this to a separate module as it is also used in seantis.dir.base
def validate_email(value):
    try:
        if value:
            checkEmailAddress(value)
    except EmailAddressInvalid:
        raise Invalid(_(u'Invalid email address'))
    return True


class EmailField(schema.TextLine):

    def __init__(self, *args, **kwargs):
        super(schema.TextLine, self).__init__(*args, **kwargs)

    def _validate(self, value):
        super(schema.TextLine, self)._validate(value)
        validate_email(value)

# referenced by configuration.zcml to register the Email fields
from plone.schemaeditor.fields import FieldFactory
EmailFieldFactory = FieldFactory(EmailField, _(u'Email'))

from plone.supermodel.exportimport import BaseHandler
EmailFieldHandler = BaseHandler(EmailField)


class IOverview(Interface):
    """ Views implementing this interface may use the OverviewletManager to
    display an overview of a list of resources. """

    def items(self):
        """ Returns a list of items to use for the overview. Each item must
        have a method 'resources' which returns a list of
        seantis.reservation.resource objects.

        """


class OverviewletManager(grok.ViewletManager):
    """ Manages the viewlets shown in the overview. """
    grok.context(Interface)
    grok.name('seantis.reservation.overviewletmanager')


class IReservationFormSet(Interface):
    """ Marks interface as usable for sub-forms in a resource object. """


class IResourceAllocationDefaults(form.Schema):

    quota = schema.Int(
        title=_(u'Quota'),
        description=_(
            u'Number of times an allocation may be reserved at the same time.'
        ),
        default=1
    )

    partly_available = schema.Bool(
        title=_(u'Partly available'),
        description=_(
            u'If the allocation is partly available users may reserve '
            u'only a part of it (e.g. half of it). If not the allocation '
            u'Must be reserved as a whole or not at all'
        ),
        default=False
    )

    raster = schema.Choice(
        title=_(u'Raster'),
        description=_(
            u'Defines the minimum length of any given reservation as well '
            u'as the alignment of the start / end of the allocation. E.g. a '
            u'raster of 30 minutes means that the allocation can only start '
            u'at xx:00 and xx:30 respectively'
        ),
        values=VALID_RASTER_VALUES,
        default=30
    )

    approve = schema.Bool(
        title=_(u'Approve reservation requests'),
        description=_(
            u'If checked a reservation manager must decide if a reservation '
            u'can be approved. Until then users are added to the waitinglist. '
            u'Reservations are automatically approved if this is not checked. '
        ),
        default=False
    )

    waitinglist_spots = schema.Int(
        title=_(u'Waiting List Spots'),
        description=_(
            u'Number of spots in the waitinglist (must be at least as high as '
            u'the quota)'
        ),
        default=100
    )

    reservation_quota_limit = schema.Int(
        title=_(u'Reservation Quota Limit'),
        description=_(
            u'The maximum quota a single reservation may occupy at once. '
            u'There is no limit if set to zero.'
        ),
        default=1
    )

    @invariant
    def isValidQuota(Allocation):
        if not (1 <= Allocation.quota and Allocation.quota <= 100):
            raise Invalid(_(u'Quota must be between 1 and 100'))

    @invariant
    def isValidWaitinglist(Allocation):
        if not Allocation.approve:
            return

        if not (Allocation.quota <= Allocation.waitinglist_spots and
                Allocation.waitinglist_spots <= 100):
            raise Invalid(
                _(u'Waitinglist length must be between the quota and 100')
            )

    @invariant
    def isValidQuotaLimit(Allocation):
        if Allocation.reservation_quota_limit < 0:
            raise Invalid(
                _(u'Reservation quota limit must zero or a positive number')
            )


class IResourceBase(IResourceAllocationDefaults):
    """ A resource displaying a calendar. """

    title = schema.TextLine(
        title=_(u'Name')
    )

    description = schema.Text(
        title=_(u'Description'),
        required=False
    )

    first_hour = schema.Int(
        title=_(u'First hour of the day'),
        description=_(
            u'Everything before this hour is not shown in the '
            u'calendar, making the calendar display more compact. '
            u'Should be set to an hour before which there cannot '
            u'be any reservations.'
        ),
        default=7
    )

    last_hour = schema.Int(
        title=_(u'Last hour of the day'),
        description=_(
            u'Everything after this hour is not shown in the '
            u'calendar, making the calendar display more compact. '
            u'Should be set to an hour after which there cannot '
            u'be any reservations.'
        ),
        default=23
    )

    form.fieldset(
        'defaults',
        label=_(u'Default Allocation Values'),
        fields=(
            'quota', 'partly_available', 'raster', 'approve',
            'waitinglist_spots', 'reservation_quota_limit'
        )
    )

    formsets = schema.List(
        title=_(u'Formsets'),
        description=_(
            u'Subforms that need to be filled out to make a reservation. '
            u'Forms can currently only be created by a site-administrator.'
        ),
        value_type=schema.Choice(
            source=form_interfaces,
        ),
        required=False
    )

    form.widget(formsets=CheckBoxFieldWidget)

    @invariant
    def isValidFirstLastHour(Resource):
        in_valid_range = lambda h: 0 <= h and h <= 24
        first_hour, last_hour = Resource.first_hour, Resource.last_hour

        if not in_valid_range(first_hour):
            raise Invalid(_(u'Invalid first hour'))

        if not in_valid_range(last_hour):
            raise Invalid(_(u'Invalid last hour'))

        if last_hour <= first_hour:
            raise Invalid(
                _(u'First hour must be smaller than last hour')
            )


class IResource(IResourceBase):
    pass


class IAllocation(IResourceAllocationDefaults):
    """ An reservable time-slot within a calendar. """

    id = schema.Int(
        title=_(u'Id'),
        default=-1,
        required=False,
    )

    group = schema.Text(
        title=_(u'Recurrence'),
        default=u'',
        required=False
    )

    timeframes = schema.Text(
        title=_(u'Timeframes'),
        default=u'',
        required=False
    )

    start_time = schema.Time(
        title=_(u'Start'),
        description=_(
            u'Allocations may start every 5 minutes if the allocation '
            u'is not partly available. If it is partly available the start '
            u'time may be every x minute where x equals the given raster.'
        )
    )

    end_time = schema.Time(
        title=_(u'End'),
        description=_(
            u'Allocations may end every 5 minutes if the allocation '
            u'is not partly available. If it is partly available the start '
            u'time may be every x minute where x equals the given raster. '
            u'The minimum length of an allocation is also either 5 minutes '
            u'or whatever the value of the raster is.'
        )
    )

    recurring = schema.Choice(
        title=_(u'Recurrence'),
        vocabulary=recurrence,
        default=False
    )

    day = schema.Date(
        title=_(u'Day'),
    )

    recurrence_start = schema.Date(
        title=_(u'From'),
    )

    recurrence_end = schema.Date(
        title=_(u'Until')
    )

    days = schema.List(
        title=_(u'Days'),
        value_type=schema.Choice(vocabulary=days),
        required=False
    )

    separately = schema.Bool(
        title=_(u'Separately reservable'),
        description=_(
            u'If checked parts of the recurrance may be reserved. '
            u'If not checkd the recurrance must be reserved as a whole.'
        ),
        required=False,
        default=False
    )

    @invariant
    def isValidRange(Allocation):
        start, end = utils.get_date_range(
            Allocation.day,
            Allocation.start_time, Allocation.end_time
        )

        if abs((end - start).seconds // 60) < 5:
            raise Invalid(_(u'The allocation must be at least 5 minutes long'))

    @invariant
    def isValidOption(Allocation):
        if Allocation.recurring:
            if Allocation.partly_available and not Allocation.separately:
                raise Invalid(_(
                    u'Partly available allocations can only be reserved '
                    u'separately'
                ))


class ITimeframe(form.Schema):
    """ A timespan which is either visible or hidden. """

    title = schema.TextLine(
        title=_(u'Name')
    )

    start = schema.Date(
        title=_(u'Start')
    )

    end = schema.Date(
        title=_(u'End')
    )

    @invariant
    def isValidDateRange(Timeframe):
        if Timeframe.start > Timeframe.end:
            raise Invalid(_(u'End date before start date'))

template_variables = _(
    u'May contain the following template variables:<br>'
    u'%(resource)s - title of the resource<br>'
    u'%(dates)s - list of dates reserved<br>'
    u'%(reservation_mail)s - email of reservee<br>'
    u'%(data)s - formdata associated with the reservation<br>'
    u'%(approval_link)s - link to the approval view<br>'
    u'%(denial_link)s - link to the denial view'
)

reservations_template_variables = _(
    u'May contain the following template variable:<br>'
    u'%(reservations)s - list of reservations'
)


class IEmailTemplate(form.Schema):
    """ An email template used for custom email messages """

    language = schema.Choice(
        title=_(u'Language'),
        source=plone_languages
    )

    reservation_pending_subject = schema.TextLine(
        title=_(u'Email Subject for Reservation Pending'),
        description=_(
            u'Sent to <b>managers</b> when a new pending reservation is made. '
            u'May contain the template variables listed below.'
        ),
        default=templates['reservation_pending'].get_subject('en')
    )

    reservation_pending_content = schema.Text(
        title=_(u'Email Text for Reservation Pending'),
        description=template_variables,
        default=templates['reservation_pending'].get_body('en')
    )

    reservation_received_subject = schema.TextLine(
        title=_(u'Email Subject for Received Reservations'),
        description=_(
            u'Sent to <b>users</b> when a new pending reservation is made. '
            u'May contain the template variables listed below.'
        ),
        default=templates['reservation_received'].get_subject('en')
    )

    reservation_received_content = schema.Text(
        title=_(u'Email Text for Received Reservations'),
        description=reservations_template_variables,
        default=templates['reservation_received'].get_body('en')
    )

    reservation_approved_subject = schema.TextLine(
        title=_(u'Email Subject for Approved Reservations'),
        description=_(u'Sent to <b>users</b> when a reservation is approved. '
                      u'May contain the template variables listed below.'),
        default=templates['reservation_approved'].get_subject('en')
    )

    reservation_approved_content = schema.Text(
        title=_(u'Email Text for Approved Reservations'),
        description=template_variables,
        default=templates['reservation_approved'].get_body('en')
    )

    reservation_denied_subject = schema.TextLine(
        title=_(u'Email Subject for Denied Reservations'),
        description=_(u'Sent to <b>users</b> when a reservation is denied. '
                      u'May contain the template variables listed below.'),
        default=templates['reservation_denied'].get_subject('en')
    )

    reservation_denied_content = schema.Text(
        title=_(u'Email Text for Denied Reservations'),
        description=template_variables,
        default=templates['reservation_denied'].get_body('en')
    )


def get_default_language(adapter):
    return utils.get_current_site_language()

DefaultLanguage = widget.ComputedWidgetAttribute(
    get_default_language, field=IEmailTemplate['language']
)


class IReservation(Interface):
    """ A reservation of an allocation (may be pending or approved). """

    id = schema.Int(
        title=_(u'Id'),
        default=-1,
        required=False
    )

    metadata = schema.TextLine(
        title=_(u'Metadata'),
        default=u'',
        required=False
    )

    day = schema.Date(
        title=_(u'Day'),
        required=False
    )

    start_time = schema.Time(
        title=_(u'Start'),
        required=False
    )

    end_time = schema.Time(
        title=_(u'End'),
        required=False
    )

    quota = schema.Int(
        title=_(u'Reservation Quota'),
        required=False,
        default=1
    )

    email = EmailField(
        title=_(u'Email'),
        required=True
    )


class IGroupReservation(Interface):
    """ A reservation of an allocation group. """

    group = schema.Text(
        title=_(u'Recurrence'),
        required=False
    )

    quota = schema.Int(
        title=_(u'Reservation Quota'),
        required=False,
        default=1
    )

    email = EmailField(
        title=_(u'Email'),
        required=True
    )


class IRemoveReservation(Interface):
    """ For the reservation removal form. """

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


class IApproveReservation(Interface):
    """ For the reservation approval form. """

    reservation = schema.Text(
        title=_(u'Reservation'),
        required=False
    )


class IReservationBaseEvent(Interface):
    """ Base Interface for reservation events (not actually fired). """

    reservation = Attribute("The reservation record associated with the event")
    language = Attribute("The language of the site or current request")


class IReservationMadeEvent(IReservationBaseEvent):
    """ Event triggered when a reservation is made (directly written or
        added to the pending reservation list).

    """


class IReservationApprovedEvent(IReservationBaseEvent):
    """ Event triggered when a reservation is approved. """


class IReservationDeniedEvent(IReservationBaseEvent):
    """ Event triggered when a reservation is denied. """


class IReservationsConfirmedEvent(Interface):
    """ Event triggered when the user confirms a list of reservations
    (i.e. submits them).

    Note how this is not a IReservationBaseEvent because it contains
    _multiple_ reservations, not just one.

    """
    reservations = Attribute("The list of reservations the user confirmed")
    language = Attribute("language of the site or current request")
