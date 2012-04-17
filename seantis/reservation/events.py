from zope.interface import implements

from seantis.reservation.interface import (
    IReservationBaseEvent,
    IReservationMadeEvent,
    IReservationApprovedEvent,
    IReservationDeniedEvent
)

class ReservationBaseEvent(object):
    implements(IReservationBaseEvent)

    def __init__(self, resource, reservation):
        self.resource = resource
        self.reservation = reservation

class ReservationMadeEvent(ReservationBaseEvent):
    implements(IReservationMadeEvent)

class ReservationApprovedEvent(ReservationBaseEvent):
    implements(IReservationApprovedEvent)

class ReservationDeniedEvent(ReservationBaseEvent):
    implements(IReservationDeniedEvent)