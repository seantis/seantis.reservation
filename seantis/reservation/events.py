from zope.interface import implements

from seantis.reservation.interfaces import (
    IReservationBaseEvent,
    IReservationMadeEvent,
    IReservationApprovedEvent,
    IReservationDeniedEvent,
    IReservationsConfirmedEvent
)


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


class ReservationsConfirmedEvent(object):
    implements(IReservationsConfirmedEvent)

    def __init__(self, reservations, language):
        self.reservations = reservations
        self.language = language
