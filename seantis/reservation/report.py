import json

from calendar import Calendar
from datetime import date, datetime, timedelta

from five import grok
from zope.interface import Interface
from plone.memoize import view

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import db
from seantis.reservation import utils
from seantis.reservation import form
from seantis.reservation.models import Allocation, Reservation
from seantis.reservation.reserve import ReservationUrls

calendar = Calendar()

class MonthlyReportView(grok.View, form.ReservationDataView):
    
    permission = 'seantis.reservation.ViewReservations'
    
    grok.require(permission)

    grok.context(Interface)
    grok.name('monthly_report') # note that this text is copied in utils.py

    template = grok.PageTemplateFile('templates/monthly_report.pt')

    @property
    def year(self):
        return int(self.request.get('year', 0))

    @property
    def month(self):
        return int(self.request.get('month', 0))

    @property
    def uuids(self):
        uuids = self.request.get('uuid', [])

        if not hasattr(uuids, '__iter__'):
            uuids = [uuids]

        return uuids

    @property
    @view.memoize
    def resources(self):
        objs = dict()

        for uuid in self.uuids:
            try:
                objs[uuid] = utils.get_resource_by_uuid(self.context, uuid).getObject()
            except AttributeError:
                continue

        return objs

    @property
    def sorted_resources(self):
        objs = self.resources

        sortkey = lambda item: self.resource_title(item[0])
        return utils.OrderedDict(sorted(objs.items(), key=sortkey))

    @property
    def statuses(self):
        return (
            ('pending', _(u'Pending')),
            ('approved', _(u'Approved')),
        )

    @view.memoize
    def resource_title(self, uuid):
        return utils.get_resource_title(self.resources[uuid])

    @property
    @view.memoize
    def min_hour(self):
        return min((r.first_hour for r in self.resources.values() if hasattr(r, 'first_hour')))

    @property
    @view.memoize
    def max_hour(self):
        return max((r.last_hour for r in self.resources.values() if hasattr(r, 'last_hour')))

    @property
    @view.memoize
    def results(self):
        return monthly_report(self.year, self.month, self.resources)

    def build_url(self, year, month):
        url = self.context.absolute_url()
        url += '/'
        url += self.__name__
        url += '?'
        url += 'year=' + str(year)
        url += '&month=' + str(month)
        url += self.show_details and '&show_details=1' or ''

        for uuid in self.uuids:
            url += '&uuid=' + uuid

        return url

    @property
    def forward_url(self):
        year, month = self.year, self.month

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        
        return self.build_url(year, month)

    def backward_url(self):
        year, month = self.year, self.month

        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1

        return self.build_url(year, month)

    @property
    def title(self):
        return _(u'Monthly Report for ${month} ${year}', mapping={
                'month': utils.month_name(self.month),
                'year': self.year
            })

    def format_day(self, day):
        return date(self.year, self.month, day).strftime('%a, %d. %m')

    def has_reservations(self, resource):
        for status in resource['lists']:
            if resource[status]:
                return True

        return False

    @property
    def show_details(self):
        return self.request.get('show_details', None) and True or False

    @property
    def data_macro_path(self):
        resource = utils.get_resource_by_uuid(self.context, self.uuids[0])
        url = resource.getURL() + '/@@reservations/macros/reservation_data'

        return url.replace(self.context.absolute_url(), 'context')

def monthly_report(year, month, resources):

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

    # store by group as it will be needed multiple times over later
    groups = dict()
    for allocation in allocations:
        groups.setdefault(allocation.group, list()).append(allocation)

    # using the groups get the relevant reservations
    query = Session.query(Reservation)
    query = query.filter(Reservation.target.in_(groups.keys()))
    query = query.order_by(Reservation.status)

    reservations = query.all()
    reservation_urls = ReservationUrls()

    used_days = []
    def add_reservation(start, end, reservation):
        day = start.day

        used_days.append(day)

        end += timedelta(microseconds=1)
        start, end = start.strftime('%H:%M'), end.strftime('%H:%M')

        context = resources[unicode(reservation.resource)]
        if reservation.status == u'approved':
            urls = [(_(u'Delete'), reservation_urls.remove_all_url(reservation.token, context))]
        elif reservation.status == u'pending':
            urls = [
                (_(u'Approve'), reservation_urls.approve_all_url(reservation.token, context)),
                (_(u'Deny'), reservation_urls.deny_all_url(reservation.token, context)),
            ]
        else:
            raise NotImplementedError

        report[day][unicode(reservation.resource)][reservation.status].append(
            dict(
                start=start, 
                end=end, 
                email=reservation.email, 
                data=reservation.data,
                timespans=json.dumps([dict(start=start, end=end)])   ,
                urls=urls,
                token=reservation.token
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
        if day not in used_days:
            del report[day]

    return report