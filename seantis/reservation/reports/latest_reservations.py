from datetime import datetime, timedelta

from five import grok
from zope.interface import Interface

from sqlalchemy import desc

from seantis.reservation import Session
from seantis.reservation import db
from seantis.reservation import _
from seantis.reservation.models import Reservation
from seantis.reservation.reports import GeneralReportParametersMixin


class LatestReservationsReportView(grok.View, GeneralReportParametersMixin):

    permission = 'seantis.reservation.ViewReservations'

    grok.require(permission)

    grok.context(Interface)
    grok.name('latest_reservations')

    template = grok.PageTemplateFile('../templates/latest_reservations.pt')

    @property
    def title(self):
        return _(u'Reservations in the last 30 days')

    @property
    def results(self):
        return latest_reservations(self.resources, self.reservations or '*')

    def reservation_title(self, reservation):
        return '{:%d.%m.%Y %H:%M} - {}'.format(
            reservation.created, reservation.title
        )

def latest_reservations(resources, reservations='*', days=30):
    schedulers = {}

    for uuid in resources.keys():
        schedulers[uuid] = db.Scheduler(uuid)

    since = datetime.today() - timedelta(days=days)

    query = Session.query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))
    query = query.filter(Reservation.created > since)
    query = query.order_by(desc(Reservation.created))

    if reservations != '*':
        query = query.filter(Reservation.token.in_(reservations))

    result = {}
    for reservation in query.all():
        if reservation.token in result:
            result.append(reservation)
        else:
            result[reservation.token] = [reservation]

    return result