from zope.interface import Attribute
from zope.interface import Interface

class ITimeRaster(Interface):
    """Defines how a timespan is divided."""
    rasterlength = Attribute("Minutes by which the time is divided")

class ITimeSpan(ITimeRaster):
    """A timespan ."""

    start = Attribute("Datetime start of the timespan.")
    end = Attribute("Datetime end of the timespan")

class IDefinedTimeSpan(ITimeSpan):
    """A defined timespan."""

    group = Attribute("Timespans with the same group belong to each other")
    resource = Attribute("Resource the timespan is referring to")
    permission = Attribute("Defines the permission needed to see the timespan")

class ITimeSlot(ITimespan):
    """A slot within a timespan."""
    definition = Attribute("Defined Timespan belonging to the timeslot")

class IReservedSlot(ITimeSpan):
    """A reserved timespan."""
    reservation = Attribute("Reservation belonging to the timeslot")



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