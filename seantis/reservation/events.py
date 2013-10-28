from zope.interface import implements

from seantis.reservation.interfaces import (
    IReservationApprovedEvent,
    IReservationBaseEvent,
    IReservationDeniedEvent,
    IReservationMadeEvent,
    IReservationRevokedEvent,
    IReservationSlotsCreatedEvent,
    IReservationsConfirmedEvent,
    IReservationSlotsRemovedEvent,
    IResourceViewedEvent,
)


class ResourceViewedEvent(object):
    implements(IResourceViewedEvent)

    def __init__(self, context):
        self.context = context


class ReservationBaseEvent(object):
    implements(IReservationBaseEvent)

    def __init__(self, reservation, language):
        self.reservation = reservation
        self.language = language


class ReservationMadeEvent(ReservationBaseEvent):
    implements(IReservationMadeEvent)


class ReservationApprovedEvent(ReservationBaseEvent):
    implements(IReservationApprovedEvent)


class ReservationDeniedEvent(ReservationBaseEvent):
    implements(IReservationDeniedEvent)


class ReservationRevokedEvent(ReservationBaseEvent):
    implements(IReservationRevokedEvent)

    def __init__(self, reservation, language, reason, send_email):
        super(ReservationRevokedEvent, self).__init__(reservation, language)
        self.reason = reason
        self.send_email = send_email


class ReservationsConfirmedEvent(object):
    implements(IReservationsConfirmedEvent)

    def __init__(self, reservations, language):
        self.reservations = reservations
        self.language = language


class ReservationSlotsCreatedEvent(ReservationBaseEvent):
    implements(IReservationSlotsCreatedEvent)


class ReservationSlotsRemovedEvent(ReservationBaseEvent):
    implements(IReservationSlotsRemovedEvent)

    def __init__(self, reservation, language, dates):
        super(ReservationSlotsRemovedEvent, self).__init__(reservation,
                                                           language)
        self.dates = dates
