from datetime import datetime
from zExceptions import NotFound

from seantis.reservation.reserve import YourReservations, ReservationForm
from seantis.reservation.session import serialized
from seantis.reservation import plone_session
from seantis.reservation.tests import IntegrationTestCase


class TestReservationForm(IntegrationTestCase):

    @serialized
    def test_reservation_data(self):
        self.login_manager()

        resource = self.create_resource()
        scheduler = resource.scheduler()

        start = datetime(2012, 12, 10, 8, 0)
        end = datetime(2012, 12, 10, 12, 0)
        dates = (start, end)
        scheduler.allocate(dates, approve_manually=False)

        request = self.portal.REQUEST
        view = YourReservations(resource, request)
        self.assertEqual(0, len(view.reservations()))

        session_id = plone_session.get_session_id(resource)
        scheduler.reserve(
            u'test@seantis.ch', dates, data={}, session_id=session_id
        )

        view = YourReservations(resource, request)
        self.assertEqual(1, len(view.reservations()))

    @serialized
    def test_allocation_property(self):
        self.login_manager()

        resource = self.create_resource()
        scheduler = resource.scheduler()

        start = datetime(2012, 12, 10, 8, 0)
        end = datetime(2012, 12, 10, 12, 0)
        allocation = scheduler.allocate((start, end))[0]

        request = self.portal.REQUEST
        form = ReservationForm(resource, request)

        self.assertEqual(form.allocation(allocation.id).id, allocation.id)
        self.assertRaises(NotFound, form.allocation, 1234)
