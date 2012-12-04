from datetime import datetime

from seantis.reservation.tests import IntegrationTestCase

from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import rasterize_end
from seantis.reservation.raster import iterate_span
from seantis.reservation.raster import VALID_RASTER_VALUES


class TestRaster(IntegrationTestCase):

    def test_rasterize(self):
        start = datetime(2011, 1, 1, 23, 14, 59)

        self.assertEqual(rasterize_start(start, 60).minute, 0)
        self.assertEqual(rasterize_start(start, 30).minute, 0)
        self.assertEqual(rasterize_start(start, 15).minute, 0)
        self.assertEqual(rasterize_start(start, 10).minute, 10)
        self.assertEqual(rasterize_start(start, 5).minute, 10)

        end = datetime(2011, 1, 1, 23, 44, 59)

        self.assertEqual(rasterize_end(end, 60).minute, 59)
        self.assertEqual(rasterize_end(end, 30).minute, 59)
        self.assertEqual(rasterize_end(end, 15).minute, 44)
        self.assertEqual(rasterize_end(end, 10).minute, 49)
        self.assertEqual(rasterize_end(end, 5).minute, 44)

        end = datetime(2011, 1, 1, 19, 0, 0)
        rastered = rasterize_end(end, 15)

        self.assertEqual(rastered.minute, 59)
        self.assertEqual(rastered.hour, end.hour - 1)

    def test_iterator(self):
        start = datetime(2011, 1, 1, 0)
        end = datetime(2011, 1, 2, 0)

        for raster in VALID_RASTER_VALUES:
            results = list(iterate_span(start, end, raster))
            self.assertEqual(len(results), 24 * 60 / raster)
