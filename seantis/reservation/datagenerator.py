from __future__ import print_function

import transaction
import random

from App.config import getConfiguration
from datetime import datetime, timedelta
from five import grok
from libres.context.session import Serializable, serialized
from libres.db.models import Allocation
from libres.modules.rasterizer import VALID_RASTER
from plone.dexterity.utils import createContentInContainer
from seantis.reservation.base import BaseView
from seantis.reservation.error import (
    OverlappingAllocationError,
    ReservationError
)
from seantis.reservation.session import Session, ILibresUtility
from zope.component import getUtility
from zope.interface import Interface


class DataGeneratorView(BaseView, Serializable):

    permission = 'cmf.ManagePortal'
    grok.require(permission)

    grok.context(Interface)
    grok.name('generate')

    template = grok.PageTemplateFile('templates/datagenerator.pt')

    @property
    def context(self):
        return getUtility(ILibresUtility).context

    @property
    def may_run(self):
        return getConfiguration().debug_mode

    @property
    def start(self):
        start = self.request.get('start', None)
        if start:
            return datetime.strptime(start, '%d.%m.%Y')
        else:
            return None

    @property
    def end(self):
        end = self.request.get('end', None)
        if end:
            return datetime.strptime(end, '%d.%m.%Y')
        else:
            return None

    @property
    def with_reservations(self):
        return bool(self.request.get('with_reservations', None))

    @property
    def min_duration(self):
        return int(self.request.get('min_duration', 30))

    @property
    def first_hour(self):
        return int(self.request.get('first_hour', 8))

    @property
    def last_hour(self):
        return int(self.request.get('last_hour', 18))

    def create_resource(self):
        resource = createContentInContainer(
            self.context, 'seantis.reservation.resource',
            title=u'random @ ' + datetime.today().strftime('%d.%m.%Y %H:%M')
        )
        resource.first_hour = self.first_hour
        resource.last_hour = self.last_hour
        return resource

    @serialized
    def generate_allocations(self, resource=None, start=None, end=None):

        today = datetime.today()

        resource = resource or self.create_resource()
        start = start or datetime(today.year, 1, 1)
        end = end or (start + timedelta(days=365))

        days = []
        for day in range(0, (end - start).days, 1):
            days.append(start + timedelta(days=day))

        scheduler = resource.scheduler()

        for day in days:

            for timespan in self.random_timespans(resource, day):

                quota = random.randrange(1, 1000)

                print('a @', timespan[0], timespan[1])

                try:
                    scheduler.allocate(
                        (timespan[0], timespan[1]),
                        raster=timespan[2],
                        partly_available=bool(random.randrange(0, 2)),
                        grouped=False,
                        quota=quota,
                        approve_manually=bool(random.randrange(0, 2))
                    )
                except OverlappingAllocationError:
                    pass

            # we must commit regularly or the postgres serial session
            # must track so many queries it goes to the barn and puts itself
            # down

            transaction.commit()

        if self.with_reservations:
            self.generate_reservations(resource, start, end)

    @serialized
    def generate_reservations(self, resource, start, end):
        query = Session.query(Allocation)
        query = query.filter(Allocation._start >= start)
        query = query.filter(Allocation._end <= end)
        query = query.filter(Allocation.mirror_of == resource.string_uuid())
        query = query.order_by(Allocation._start)

        email = 'generated@example.com'
        scheduler = resource.scheduler()

        allocations = query.all()
        Session.expunge_all()

        for allocation in allocations:

            if allocation.partly_available:
                start = allocation.start
                total = (allocation.end - allocation.start).seconds / 60

                if total > allocation.raster:
                    start_minute = random.randrange(
                        0, total - allocation.raster, allocation.raster
                    )
                    end_minute = random.randrange(
                        start_minute + allocation.raster, total,
                        allocation.raster
                    )
                else:
                    start_minute = 0
                    end_minute = total

                start = start + timedelta(start_minute * 60)
                end = start + timedelta(end_minute * 60)
            else:
                start, end = allocation.start, allocation.display_end

            if not allocation.approve_manually:
                limit = allocation.quota

            for i in range(0, random.randrange(0, limit + 1)):
                try:
                    print('r @', start, end)
                    token = scheduler.reserve(email, dates=(start, end))
                    if not allocation.approve_manually:
                        scheduler.approve_reservations(token)
                except ReservationError:
                    break

            Session.expire_on_commit = False
            transaction.commit()

    def random_raster(self):
        return random.choice(VALID_RASTER)

    def random_timespans(self, resource, day):

        day = day or datetime.today()

        min_minute = resource.first_hour * 60
        max_minute = resource.last_hour * 60

        timespans = []

        base = datetime(day.year, day.month, day.day)

        while True:
            raster = self.random_raster()
            offset = max(raster, self.min_duration)

            if max_minute - min_minute <= offset:
                break

            start_minute = random.randrange(
                min_minute, max_minute - offset, raster
            )
            end_minute = random.randrange(
                start_minute + offset, max_minute, raster
            )

            start = base + timedelta(seconds=start_minute * 60)
            end = base + timedelta(seconds=end_minute * 60)

            timespans.append((start, end, raster))

            min_minute = end_minute

        return timespans

    def update(self, *args, **kwargs):
        super(DataGeneratorView, self).update(*args, **kwargs)

        if self.may_run and self.request.get('generate_data'):
            self.generate_allocations(start=self.start, end=self.end)
            print("done!")
