import json

from calendar import Calendar
from datetime import date, timedelta, datetime

from five import grok
from zope.interface import Interface
from plone.memoize import view

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import settings
from seantis.reservation import utils
from libres import modules
from libres.db.models import Allocation, Reservation
from seantis.reservation.reports import GeneralReportParametersMixin
from seantis.reservation.interfaces import ISeantisReservationSpecific

calendar = Calendar()


class MonthlyReportView(
    grok.View, GeneralReportParametersMixin
):

    permission = 'seantis.reservation.ViewReservations'

    grok.require(permission)

    grok.context(Interface)
    grok.layer(ISeantisReservationSpecific)
    grok.name('monthly_report')  # note that this text is copied in utils.py

    template = grok.PageTemplateFile('../templates/monthly_report.pt')

    @property
    def title(self):
        return _(
            u'Monthly Report for ${month} ${year}',
            mapping={
                'month': utils.month_name(
                    self.context, self.request, self.month
                ),
                'year': self.year
            }
        )

    @property
    def year(self):
        return int(self.request.get('year', date.today().year))

    @property
    def month(self):
        return int(self.request.get('month', date.today().month))

    @property
    @view.memoize
    def min_hour(self):
        return min(
            (r.first_hour for r in self.resources.values()
                if hasattr(r, 'first_hour'))
        )

    @property
    @view.memoize
    def max_hour(self):
        return max(
            (r.last_hour for r in self.resources.values()
                if hasattr(r, 'last_hour'))
        )

    @property
    @view.memoize
    def results(self):
        return monthly_report(
            self.year, self.month, self.resources, self.reservations or '*'
        )

    @property
    def show_timetable(self):
        # hide_timetable is the query parameter as showing is the default
        return False if self.request.get('hide_timetable') else True

    def build_url(self, year, month):
        params = [
            ('year', str(year)),
            ('month', str(month))
        ]

        if not self.show_timetable:
            params.append(('hide_timetable', '1'))

        return super(MonthlyReportView, self).build_url(
            extra_parameters=params
        )

    @property
    def forward_url(self):
        year, month = self.year, self.month

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

        return self.build_url(year, month)

    @property
    def backward_url(self):
        year, month = self.year, self.month

        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1

        return self.build_url(year, month)

    def format_day(self, day):
        daydate = datetime(self.year, self.month, day)
        weekday = utils.weekdayname_abbr(
            self.context, self.request, utils.shift_day(daydate.weekday())
        )

        return ', '.join((
            weekday,
            utils.localize_date(daydate, long_format=False)
        ))

    def has_reservations(self, resource):
        for status in resource['lists']:
            if resource[status]:
                return True

        return False


def monthly_report(year, month, resources, reservations='*'):

    titles = dict()

    for uuid in resources.keys():
        titles[uuid] = utils.get_resource_title(resources[uuid])

    # timezone of the report
    timezone = settings.timezone()

    # this order is used for every day in the month
    ordered_uuids = [i[0] for i in sorted(titles.items(), key=lambda i: i[1])]

    # build the hierarchical structure of the report data
    report = utils.OrderedDict()
    last_day = 28

    for d in sorted((d for d in calendar.itermonthdates(year, month))):
        if not d.month == month:
            continue

        day = d.day
        last_day = max(last_day, day)
        report[day] = utils.OrderedDict()

        for uuid in ordered_uuids:
            report[day][uuid] = dict()
            report[day][uuid][u'title'] = titles[uuid]
            report[day][uuid][u'approved'] = list()
            report[day][uuid][u'pending'] = list()
            report[day][uuid][u'url'] = resources[uuid].absolute_url()
            report[day][uuid][u'lists'] = {
                u'approved': _(u'Approved'),
                u'pending': _(u'Pending'),
            }

    # gather the reservations with as much bulk loading as possible
    period_start = datetime(year, month, 1, tzinfo=timezone)
    period_end = datetime(year, month, last_day, tzinfo=timezone)
    period_end += timedelta(days=1, microseconds=-1)

    # get a list of relevant allocations in the given period
    query = Session().query(Allocation)
    query = query.filter(period_start <= Allocation._start)
    query = query.filter(Allocation._start <= period_end)
    query = query.filter(Allocation.resource == Allocation.mirror_of)
    query = query.filter(Allocation.resource.in_(resources.keys()))

    allocations = query.all()

    # quit if there are no allocations at this point
    if not allocations:
        return {}

    # store by group as it will be needed multiple times over later
    groups = dict()
    for allocation in allocations:
        groups.setdefault(allocation.group, list()).append(allocation)

    # using the groups get the relevant reservations
    query = Session().query(Reservation)
    query = query.filter(Reservation.target.in_(groups.keys()))

    if reservations != '*':
        query = query.filter(Reservation.token.in_(reservations))

    query = query.order_by(Reservation.status)

    reservations = query.all()

    @utils.memoize
    def json_timespans(start, end):
        return json.dumps([dict(start=start, end=end)])

    used_days = dict([(i, False) for i in range(1, 32)])
    timezone = settings.timezone()

    def add_reservation(start, end, reservation):
        day = start.day

        used_days[day] = True

        end += timedelta(microseconds=1)

        start = modules.calendar.to_timezone(start, timezone=timezone)
        end = modules.calendar.to_timezone(end, timezone=timezone)

        start = utils.localize_date(start, time_only=True)
        end = utils.localize_date(end, time_only=True)

        context = resources[utils.string_uuid(reservation.resource)]

        reservation_lists = report[day][utils.string_uuid(
            reservation.resource
        )]
        reservation_lists[reservation.status].append(
            dict(
                start=start,
                end=end,
                email=reservation.email,
                data=reservation.data,
                timespans=json_timespans(start, end),
                id=reservation.id,
                token=reservation.token,
                quota=utils.get_reservation_quota_statement(reservation.quota),
                resource=context,
            )
        )

    for reservation in reservations:
        if reservation.target_type == u'allocation':
            add_reservation(reservation.start, reservation.end, reservation)
        else:
            for allocation in groups[reservation.target]:
                add_reservation(allocation.start, allocation.end, reservation)

    # remove unused days
    for day in report:
        if not used_days[day]:
            del report[day]

    return report
