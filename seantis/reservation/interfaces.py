from zope.interface import Interface

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