from seantis.reservation import utils
from seantis.reservation.tests import IntegrationTestCase

class UtilsTestCase(IntegrationTestCase):

    def test_pairs(self):
        one = ('aa','bb','cc','dd')
        two = (('aa','bb'), ('cc', 'dd'))

        self.assertEqual(utils.pairs(one), utils.pairs(two))