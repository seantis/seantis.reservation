from datetime import datetime

from seantis.reservation.reserve import MyReservations
from seantis.reservation.session import serialized
from seantis.reservation import plone_session
from seantis.reservation.tests import IntegrationTestCase


class TestMyReservations(IntegrationTestCase):

    @serialized
    def test_reservation_data(self):
        self.login_as_manager()

        resource = self.create_resource()
        scheduler = resource.scheduler()

        start = datetime(2012, 12, 10, 8, 0)
        end = datetime(2012, 12, 10, 12, 0)
        dates = (start, end)
        scheduler.allocate(dates, approve=False)

        request = self.portal.REQUEST
        view = MyReservations(resource, request)
        self.assertEqual(0, len(view.reservations()))

        session_id = plone_session.get_session_id(resource)
        scheduler.reserve(
            u'test@seantis.ch', dates, data={}, session_id=session_id
        )

        view = MyReservations(resource, request)
        self.assertEqual(1, len(view.reservations()))