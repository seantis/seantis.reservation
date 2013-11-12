import json

from calendar import Calendar
from datetime import date, time, timedelta

from five import grok
from zope.interface import Interface
from plone.memoize import view

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import db
from seantis.reservation import utils
from seantis.reservation.models import Allocation, Reservation
from seantis.reservation.reserve import ReservationUrls
from seantis.reservation.reports import GeneralReportParametersMixin

calendar = Calendar()


class MonthlyReportView(
    grok.View, GeneralReportParametersMixin
):

    permission = 'seantis.reservation.ViewReservations'

    grok.require(permission)

    grok.context(Interface)
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
        daydate = date(self.year, self.month, day)
        weekday = utils.weekdayname_abbr(
            self.context, self.request, utils.shift_day(daydate.weekday())
        )
        return weekday + daydate.strftime(', %d. %m')

    def has_reservations(self, resource):
        for status in resource['lists']:
            if resource[status]:
                return True

        return False

    def merged_divisions(self, reservation):
        """Calculate timetable cells for display in reports.

        Converted from jquery.timetable.js to python.

        """
        start, end = reservation['start'], reservation['end']
        if start.hour < self.min_hour:
            start = time(self.min_hour, 0)
        if end.hour > self.max_hour:
            end = time(self.max_hour, 0)

        text = "{} - {}".format(start.strftime('%H:%M'), end.strftime('%H:%M'))

        result = []
        for hour in range(self.min_hour, self.max_hour):

            # outside of start & end are the free cells
            if hour < start.hour or end.hour < hour:
                result.append(dict(left=0.0, right=0.0, span=1.0, state='free',
                                   text=''))
                continue

            # one single occupied cell
            if hour == start.hour and hour == end.hour:
                result.append(dict(
                    left=(start.minute / 60.0) * 100,
                    right=((60.0 - end.minute) / 60.0) * 100,
                    span=1.0,
                    state='occupied',
                    text=text
                ))
                continue

            #a item which will span multiple cells
            if hour == start.hour:
                result.append(dict(
                    left=(start.minute / 60.0) * 100,
                    right=0.0,
                    span=1.0,
                    state='occupied',
                    text=text
                ))
                continue

            previous = result[-1]

            # increment span of most recent item
            if start.hour < hour and hour < end.hour:
                previous['span'] += 1
                continue

            # close last item
            if hour == end.hour:
                # if the hour ends on zero the last cell is free
                if end.minute == 0:
                    result.append(dict(
                        left=0.0, right=0.0, state='free', span=1.0
                    ))
                else:
                    previous['right'] = ((60 - end.minute) / 60.0) * 100
                    previous['span'] += 1

                previous['left'] = (previous['left'] /
                                    (previous['span'] * 100)) * 100
                previous['right'] = (previous['right'] /
                                     (previous['span'] * 100)) * 100
                continue

        for each in result:
            left = each['left']
            right = each['right']
            middle = 100 - left - right
            style = "width: {}%; margin-left: {}%; margin-right: {}%;"
            each['style'] = style.format(middle, left, right)

        return result


def monthly_report(year, month, resources, reservations='*'):

    schedulers, titles = dict(), dict()

    for uuid in resources.keys():
        schedulers[uuid] = db.Scheduler(uuid)
        titles[uuid] = utils.get_resource_title(resources[uuid])

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
    period_start = date(year, month, 1)
    period_end = date(year, month, last_day)

    # get a list of relevant allocations in the given period
    query = Session.query(Allocation)
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
    query = Session.query(Reservation)
    query = query.filter(Reservation.target.in_(groups.keys()))

    if reservations != '*':
        query = query.filter(Reservation.token.in_(reservations))

    query = query.order_by(Reservation.status)

    reservations = query.all()
    reservation_urls = ReservationUrls()

    @utils.memoize
    def json_timespans(start, end):
        return json.dumps([dict(start=start, end=end)])

    used_days = dict([(i, False) for i in range(1, 32)])

    def add_reservation(start, end, reservation):
        day = start.day

        used_days[day] = True

        end += timedelta(microseconds=1)
        start_fmt, end_fmt = start.strftime('%H:%M'), end.strftime('%H:%M')

        context = resources[utils.string_uuid(reservation.resource)]

        if reservation.status == u'approved':
            rightside_urls = [(
                _(u'Delete'),
                reservation_urls.revoke_all_url(reservation.token, context)
            )]
        elif reservation.status == u'pending':
            rightside_urls = [
                (
                    _(u'Approve'),
                    reservation_urls.approve_all_url(
                        reservation.token, context
                    )
                ),
                (
                    _(u'Deny'),
                    reservation_urls.deny_all_url(reservation.token, context)
                ),
            ]
        else:
            raise NotImplementedError

        reservation_lists = report[day][utils.string_uuid(
            reservation.resource
        )]
        reservation_lists[reservation.status].append(
            dict(
                start=start,
                end=end,
                email=reservation.email,
                data=reservation.data,
                timespans=dict(start=start_fmt, end=end_fmt),
                rightside_urls=rightside_urls,
                token=reservation.token,
                quota=utils.get_reservation_quota_statement(reservation.quota),
                resource=context
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
