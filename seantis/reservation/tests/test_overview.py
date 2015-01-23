from datetime import datetime
from libres.context.session import serialized
from pytz import timezone
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.overview import Overview


class TestOverview(IntegrationTestCase):

    @serialized
    def test_overview(self):
        self.login_manager()

        r1 = self.create_resource()
        r2 = self.create_resource()

        scheduler = r1.scheduler()

        start = datetime(2015, 1, 23, 12, 0)
        end = datetime(2015, 1, 23, 15, 0)
        scheduler.allocate((start, end), approve_manually=False)

        scheduler = r2.scheduler()

        start = datetime(2015, 1, 23, 12, 0)
        end = datetime(2015, 1, 23, 15, 0)
        scheduler.allocate((start, end), approve_manually=False)

        overview = Overview(r1, self.request())
        events = overview.events(
            daterange=(
                datetime(2015, 1, 21, tzinfo=timezone('UTC')),
                datetime(2015, 1, 24, tzinfo=timezone('UTC'))
            ),
            uuids=[r1.uuid(), r2.uuid()]
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['className'], 'event-available')

        scheduler.approve_reservations(
            scheduler.reserve(u'test@example.org', (start, end))
        )

        events = overview.events(
            daterange=(
                datetime(2015, 1, 21, tzinfo=timezone('UTC')),
                datetime(2015, 1, 24, tzinfo=timezone('UTC'))
            ),
            uuids=[r1.uuid(), r2.uuid()]
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['className'], 'event-partly-available')
