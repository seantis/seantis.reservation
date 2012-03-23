import json

from calendar import Calendar
from datetime import date, timedelta

from five import grok
from zope.interface import Interface
from plone.memoize import view

from seantis.reservation import Session
from seantis.reservation import db
from seantis.reservation import utils
from seantis.reservation import form
from seantis.reservation.models import Allocation, Reservation

calendar = Calendar()

class MonthlyReportView(grok.View, form.ReservationDataView):
    permission = 'cmf.ManagePortal'

    grok.context(Interface)
    grok.name('monthly_report')
    grok.require('zope2.View')

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
    def results(self):
        return monthly_report(self.context, self.year, self.month, self.uuids)

    @view.memoize
    @property
    def data_macro_path(self):
        resource = utils.get_resource_by_uuid(self.context, self.uuids[0])
        url = resource.getURL() + '/@@reservations/macros/reservation_data'

        return url.replace(self.context.absolute_url(), 'context')

def monthly_report(context, year, month, resource_uuids):

    resources, schedulers, titles = dict(), dict(), dict()

    for uuid in resource_uuids:
        schedulers[uuid] = db.Scheduler(uuid)
        resources[uuid] = utils.get_resource_by_uuid(context, uuid).getObject()
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

    # gather the reservations with as much bulk loading as possible
    period_start = date(year, month, 1)
    period_end = date(year, month, last_day)

    # get a list of relevant allocations in the given period
    query = Session.query(Allocation)
    query = query.filter(period_start <= Allocation._start)
    query = query.filter(Allocation._start <= period_end)
    query = query.filter(Allocation.resource == Allocation.mirror_of)
    query = query.filter(Allocation.resource.in_(resource_uuids))

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

    def add_reservation(start, end, reservation):
        day = start.day
        end += timedelta(microseconds=1)
        start, end = start.strftime('%H:%M'), end.strftime('%H:%M')
        report[day][unicode(reservation.resource)][reservation.status].append(
            dict(start=start, end=end, email=reservation.email, data=reservation.data)
        )

    for reservation in reservations:
        if reservation.target == u'allocation':
            add_reservation(reservation.start, reservation.end, reservation)
        else:
            for allocation in groups[reservation.target]:
                add_reservation(allocation.start, allocation.end, reservation)

    return report