from datetime import datetime, timedelta

from five import grok
from zope.interface import Interface

from sqlalchemy import desc

from seantis.reservation import Session
from seantis.reservation import db
from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.models import Reservation
from seantis.reservation.reports import GeneralReportParametersMixin


def human_date(date):
    # timezones are currently naive and implicity the the one used by
    # the users - we don't have international reservations yet
    now = utils.utcnow()

    this_morning = datetime(
        now.year, now.month, now.day
    ).replace(tzinfo=now.tzinfo)

    time = date.strftime('%H:%M')

    if date >= this_morning:
        return _(u'Today, at ${time}', mapping={'time': time})

    days = (now.date() - date.date()).days

    if days <= 1:
        return _(u'Yesterday, at ${time}', mapping={
            'time': time
        })
    else:
        return _(u'${days} days ago, at ${time}', mapping={
            'days': days,
            'time': time
        })


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
        human_date_text = utils.translate(
            self.context, self.request, human_date(reservation.created)
        )
        return '{} - {}'.format(human_date_text, reservation.title)


def latest_reservations(resources, reservations='*', days=30):
    schedulers = {}

    for uuid in resources.keys():
        schedulers[uuid] = db.Scheduler(uuid)

    since = utils.utcnow() - timedelta(days=days)

    query = Session.query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))
    query = query.filter(Reservation.created > since)
    query = query.order_by(desc(Reservation.created))

    if reservations != '*':
        query = query.filter(Reservation.token.in_(reservations))

    result = utils.OrderedDict()
    for reservation in query.all():
        if reservation.token in result:
            result.append(reservation)
        else:
            result[reservation.token] = [reservation]

    return result