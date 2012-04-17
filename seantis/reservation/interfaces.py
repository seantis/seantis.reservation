from dateutil import rrule

from five import grok

from zope import schema
from zope.interface import Interface, invariant, Invalid, Attribute
from zope.component import getAllUtilitiesRegisteredFor as getallutils
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.directives import form
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import schemaNameToPortalType as getname

from z3c.form.browser.checkbox import CheckBoxFieldWidget
from seantis.reservation import _, utils
from seantis.reservation.raster import VALID_RASTER_VALUES
from seantis.reservation.email import EmailField

days = SimpleVocabulary(
        [SimpleTerm(value=rrule.MO, title=_(u'Mo')),
         SimpleTerm(value=rrule.TU, title=_(u'Tu')),
         SimpleTerm(value=rrule.WE, title=_(u'We')),
         SimpleTerm(value=rrule.TH, title=_(u'Th')),
         SimpleTerm(value=rrule.FR, title=_(u'Fr')),
         SimpleTerm(value=rrule.SA, title=_(u'Sa')),
         SimpleTerm(value=rrule.SU, title=_(u'Su')),
        ]
    )
    
recurrence = SimpleVocabulary(
        [SimpleTerm(value=False, title=_(u'Once')),
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
    interfaces = [(u.title, u.lookupSchema()) for u in dutils if behavior in u.behaviors]
    
    def get_term(item):
        return SimpleTerm(title=item[0], value=getname(item[1].__name__))

    return SimpleVocabulary(map(get_term, interfaces))

class IOverview(Interface):
    """ Views implementing this interface may use the OverviewletManager to
    display an overview of a list of resources. """

    def items(self):
        """ Returns a list of items to use for the overview. Each item must have
        a method 'resources' which returns a list of seantis.reservation.resource
        objects.

        """

class OverviewletManager(grok.ViewletManager):
    """ Manages the viewlets shown in the overview. """
    grok.context(Interface)
    grok.name('seantis.reservation.overviewletmanager')

class IReservationFormSet(Interface):
    """ Marks interface as usable for sub-forms in a resource object. """

class IResourceBase(form.Schema):
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
            default=0
        )

    last_hour = schema.Int(
            title=_(u'Last hour of the day'),
            default=24
        )

    quota = schema.Int(
            title=_(u'Quota'),
            default=1
        )

    formsets = schema.List(
            title=_(u'Formsets'),
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

class IAllocation(form.Schema):
    """ An reservable time-slot within a calendar. """

    id = schema.Int(
        title=_(u'Id'),
        default=-1,
        required=False
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
        title=_(u'Start')
        )

    end_time = schema.Time(
        title=_(u'End')
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
        required=False,
        default=False
        )

    partly_available = schema.Bool(
        title=_(u'Partly available'),
        default=False
        )

    raster = schema.Choice(
        title=_(u'Raster'),
        values=VALID_RASTER_VALUES,
        default=30
        )

    quota = schema.Int(
        title=_(u'Quota'),
        )

    approve = schema.Bool(
        title=_(u'Approve reservation requests'),
        default=False
        )
    
    waitinglist_spots = schema.Int(
        title=_(u'Waiting List Spots'),
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
    def isValidQuota(Allocation):
        if not (1 <= Allocation.quota and Allocation.quota <= 100):
            raise Invalid(_(u'Quota must be between 1 and 100'))

    @invariant
    def isValidWaitinglist(Allocation):    
        if not (Allocation.quota <= Allocation.waitinglist_spots and Allocation.waitinglist_spots <= 100):
            raise Invalid(_(u'Waitinglist length must be between the quota and 100'))

    @invariant
    def isValidOption(Allocation):
        if Allocation.recurring:
            if Allocation.partly_available and not Allocation.separately:
                raise Invalid(_(u'Partly available allocations can only be reserved separately'))

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

class IReservationMadeEvent(Interface):
    """ Event triggered when a reservation is made (directly written or
        added to the pending reservation list).

    """

    resource = Attribute("The resource on which the reservaiton was made")
    reservation = Attribute("The reservation record")

class IReservationDecisionBaseEvent(Interface):
    """ Base-Interface for Approved / Denied Reservations (not actually fired)."""

    resource = Attribute("The resource the decision was made on")
    reservation = Attribute("The approved or denied reservation")


class IReservationApprovedEvent(IReservationDecisionBaseEvent):
    pass

class IReservationDeniedEvent(IReservationDecisionBaseEvent):
    pass