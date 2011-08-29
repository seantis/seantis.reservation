from zope.interface import Attribute
from zope.interface import Interface

class ITimeSlot(Interface):
    """A timeslot that may refer to one or many time ranges."""

    start = Attribute("Datetime start of the timeslot.")
    end = Attribute("Datetime end of the timeslot")
    group = Attribute("Key of other timeslots that belong to this timeslot")
    resource = Attribute("Resource the timeslot is referring to")
    permission = Attribute("Defines the permission needed to see the timeslot")


class IAvailableSlot(ITimeSlot):
    """An available timeslot."""


class IReservedSlot(ITimeSlot):
    """A reserved timeslot."""


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

    def request(timeslot):
        """Requests the resource at timeslot and returns a reservation id."""