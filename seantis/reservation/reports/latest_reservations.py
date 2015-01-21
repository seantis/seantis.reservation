from datetime import datetime, timedelta

from five import grok
from zope.interface import Interface

from sqlalchemy import desc

from seantis.reservation import Session
from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.reservations import combine_reservations
from libres.db.models import Reservation
from seantis.reservation.base import BaseView
from seantis.reservation.reports import GeneralReportParametersMixin


def human_date(date):
    # timezones are currently naive and implicity the one used by
    # the users - we don't have international reservations yet
    now = utils.utcnow()

    this_morning = datetime(
        now.year, now.month, now.day
    ).replace(tzinfo=now.tzinfo)

    time = utils.localize_date(date, time_only=True)

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


class LatestReservationsReportView(BaseView, GeneralReportParametersMixin):

    permission = 'seantis.reservation.ViewReservations'

    grok.require(permission)

    grok.context(Interface)
    grok.name('latest_reservations')

    template = grok.PageTemplateFile('../templates/latest_reservations.pt')

    @property
    def title(self):
        return _(u'Latest Reservations')

    @property
    def start(self):
        return utils.safe_parse_int(self.request.get('start'), 0)

    @property
    def end(self):
        return utils.safe_parse_int(self.request.get('end'), 30)

    @property
    def results(self):
        return latest_reservations(
            resources=self.resources,
            reservations=self.reservations or '*',
            daterange=self.daterange,
        )

    @property
    def daterange(self):
        now = utils.utcnow()

        since = now - timedelta(days=self.end)
        until = now - timedelta(days=self.start)

        return since, until

    @property
    def daterange_label(self):
        since, until = self.daterange

        if until.date() == utils.utcnow().date():
            return ' - '.join((
                utils.localize_date(since, long_format=False),
                self.translate(_(u'Today'))
            ))
        return ' - '.join((
            utils.localize_date(since, long_format=False),
            utils.localize_date(until, long_format=False)
        ))

    def build_url(self, start, end):
        params = [
            ('start', str(start)),
            ('end', str(end))
        ]

        return super(LatestReservationsReportView, self).build_url(
            extra_parameters=params
        )

    @property
    def forward_url(self):
        start, end = self.start, self.end
        start, end = start - 30, end - 30

        if start < 0:
            return None

        return self.build_url(start, end)

    @property
    def backward_url(self):
        start, end = self.start, self.end
        start, end = start + 30, end + 30

        return self.build_url(start, end)

    def reservation_title(self, reservation):
        human_date_text = utils.translate(
            self.context, self.request, human_date(reservation.created)
        )
        return '{} - {}'.format(human_date_text, reservation.title)

    def unique(self, reservations):
        return tuple(combine_reservations(reservations))


def latest_reservations(resources, daterange, reservations='*'):
    query = Session().query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))
    query = query.filter(Reservation.created > daterange[0])
    query = query.filter(Reservation.created <= daterange[1])
    query = query.order_by(desc(Reservation.created))

    if reservations != '*':
        query = query.filter(Reservation.token.in_(reservations))

    result = utils.OrderedDict()
    for reservation in query.all():
        if reservation.token in result:
            result[reservation.token].append(reservation)
        else:
            result[reservation.token] = [reservation]

    return result
