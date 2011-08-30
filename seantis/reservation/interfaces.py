from zope.interface import Attribute
from zope.interface import Interface

class ITimeSpan(Interface):
    """A timespan that may refer to one or many time ranges."""

    start = Attribute("Datetime start of the timespan.")
    end = Attribute("Datetime end of the timespan")
    group = Attribute("Key of other timespans that belong to this timespan")
    resource = Attribute("Resource the timespan is referring to")
    permission = Attribute("Defines the permission needed to see the timespan")


class IAvailableSlot(ITimeSpan):
    """An available timespan."""


class IReservedSlot(ITimeSpan):
    """A reserved timespan."""


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