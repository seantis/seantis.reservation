from zope.component.hooks import getSite

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation import maintenance


class TestMaintenance(IntegrationTestCase):

    def test_register_once_per_connection(self):

        once = maintenance.register_once_per_connection
        self.assertTrue(once('/test', getSite(), 1))
        self.assertFalse(once('/test', getSite(), 1))
        self.assertFalse(once('/test2', getSite(), 1))

        self.assertEqual(1, len(maintenance._clockservers))
