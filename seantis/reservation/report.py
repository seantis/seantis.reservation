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

calendar = Calendar()

class MonthlyReportView(grok.View, form.ReservationDataView):
    permission = 'cmf.ManagePortal'
    grok.require(permission)

    grok.context(Interface)
    grok.name('monthly_report')

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
            objs[uuid] = utils.get_resource_by_uuid(self.context, uuid).getObject()

        return objs

    @property
    @view.memoize
    def min_hour(self):
        return min((r.first_hour for r in self.resources.values()))

    @property
    @view.memoize
    def max_hour(self):
        return max((r.last_hour for r in self.resources.values()))

    @property
    @view.memoize
    def results(self):
        return monthly_report(self.year, self.month, self.resources)

    @property
    def title(self):
        return _(u'Monthly Report for %(month)s %(year)i') % dict(
            month=utils.month_name(self.month), year=self.year
        )

    def format_day(self, day):
        return date(self.year, self.month, day).strftime('%a, %d. %m')

    def has_reservations(self, resource):
        for status in resource['lists']:
            if resource[status]:
                return True

        return False

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
    for day in sorted((d.day for d in calendar.itermonthdates(year, month))):
        last_day = max(last_day, day)
        report[day] = dict()
        
        for uuid in ordered_uuids:    
            report[day][uuid] = dict()
            report[day][uuid][u'title'] = titles[uuid]
            report[day][uuid][u'approved'] = list()
            report[day][uuid][u'pending'] = list()
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

    used_days = []
    def add_reservation(start, end, reservation):
        day = start.day

        used_days.append(day)

        end += timedelta(microseconds=1)
        start, end = start.strftime('%H:%M'), end.strftime('%H:%M')
        report[day][unicode(reservation.resource)][reservation.status].append(
            dict(
                start=start, 
                end=end, 
                email=reservation.email, 
                data=reservation.data,
                timespans=json.dumps([dict(start=start, end=end)])   
            )
        )

    for reservation in reservations:
        if reservation.target == u'allocation':
            add_reservation(reservation.start, reservation.end, reservation)
        else:
            for allocation in groups[reservation.target]:
                add_reservation(allocation.start, allocation.end, reservation)

    # remove unused days
    for day in report:
        if day not in used_days:
            del report[day]

    return report