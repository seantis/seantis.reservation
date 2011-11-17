from datetime import datetime, timedelta
from dateutil import rrule

from zope.interface import Interface
from plone.directives import form
from zope import schema
from zope import interface

from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm

from seantis.reservation import utils
from seantis.reservation.raster import VALID_RASTER_VALUES
from seantis.reservation import _

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

class IReservable(Interface):
    """Reservable object."""

    def uid(self):
        """Returns a unique key for the resource."""

class IReservationCallback(Interface):
    """Handles callbacks of the reservation manager."""

    def confirm(reservation):
        """Confirms the given reservation."""

    def deny(reservation):
        """Denies the given reservation."""

class IReservationManager(Interface):
    """Handles reservations."""

    def register(callback):
        """Registers the IReservationCallback object"""

    def request(timespan):
        """Requests the resource at timespan and returns a reservation id."""

class IResourceBase(form.Schema):

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

    @interface.invariant
    def isValidFirstLastHour(Resource):
        in_valid_range = lambda h: 0 <= h and h <= 24
        first_hour, last_hour = Resource.first_hour, Resource.last_hour
        
        if not in_valid_range(first_hour):
            raise interface.Invalid(_(u'Invalid first hour'))

        if not in_valid_range(last_hour):
            raise interface.Invalid(_(u'Invalid last hour'))

        if last_hour <= first_hour:
            raise interface.Invalid(
                    _(u'First hour must be smaller than last hour')
                )                  

class IResource(IResourceBase):
    pass

class IAllocation(form.Schema):

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

    @interface.invariant
    def isValidRange(Allocation):
        start, end = utils.get_date_range(
                Allocation.day, 
                Allocation.start_time, Allocation.end_time
            )
        
        if abs((end - start).seconds // 60) < 5:
            raise interface.Invalid(_(u'The allocation must be at least 5 minutes long'))

    @interface.invariant
    def isValidQuota(Allocation):
        if not (1 <= Allocation.quota and Allocation.quota <= 100):
            raise interface.Invalid(_(u'Quota must be between 1 and 100'))

    @interface.invariant
    def isValidOption(Allocation):
        if Allocation.recurring:
            if Allocation.partly_available and not Allocation.separately:
                raise interface.Invalid(_(u'Partly available allocations can only be reserved separately'))

class ITimeframe(form.Schema):

    title = schema.TextLine(
            title=_(u'Name')
        )

    start = schema.Date(
            title=_(u'Start')
        )

    end = schema.Date(
            title=_(u'End')
        )

    @interface.invariant
    def isValidDateRange(Timeframe):
        if Timeframe.start > Timeframe.end:
            raise interface.Invalid(_(u'End date before start date'))

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

class IGroupReservation(interface.Interface):

    group = schema.Text(
        title=_(u'Recurrence'),
        required=False
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