from plone.app.testing import TEST_USER_ID

from seantis.reservation.session import serialized
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.mail import get_managers_by_context


class MailTestCase(IntegrationTestCase):

    @serialized
    def test_manager_discovery(self):
        self.login_manager()

        resource = self.create_resource()

        # nobody's defined in the hierarchy, in which case anybody with the
        # reservation role get's the email
        self.set_test_user_roles(['Manager', 'Reservation-Manager'])
        self.assertEqual(get_managers_by_context(resource), [TEST_USER_ID])

        # if we assign two separate managers to the resource we should
        # only get those
        self.assign_reservation_manager('ted@example.com', resource)
        self.assign_reservation_manager('brad@example.com', resource)

        self.assertEqual(
            sorted(get_managers_by_context(resource)),
            sorted(['ted', 'brad'])
        )
