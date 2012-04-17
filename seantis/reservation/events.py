from zope.interface import implements

from seantis.reservation.interfaces import (
    IReservationBaseEvent,
    IReservationMadeEvent,
    IReservationApprovedEvent,
    IReservationDeniedEvent
)

class ReservationBaseEvent(object):
    implements(IReservationBaseEvent)

    def __init__(self, reservation):
        self.reservation = reservation

class ReservationMadeEvent(ReservationBaseEvent):
    implements(IReservationMadeEvent)

class ReservationApprovedEvent(ReservationBaseEvent):
    implements(IReservationApprovedEvent)

class ReservationDeniedEvent(ReservationBaseEvent):
    implements(IReservationDeniedEvent)