"""The rasterizing functions ensure that all timespans and their timeslots
confirm to a specific raster. This means that start and end dates cannot begin
just at any time. Instead they can begin at 00:00, 00:15, 00:30, 00:45 etc.
depending on the used raster.

This is done because it is an easy way to ensure that no reservations overlap.

Consider the following reservations:
1 19:01 - 19:30
2 19:00 - 19:29

These reservations do overlap, but to know that it would be necessary to
compare each new reservation with the existing reservation. This is not only
expensive, but it also does not ensure that no reservations overlap if
reservations are added at the same time in a multiuser environment.

By rasterizing the above reservations with a raster of 30 minutes
we end up with these times:
1 19:00 - 19:29:59:9999
2 19:00 - 19:29:59:9999

In fact any time between 19 and 19:30 will either snap to 19:00 (start)
or 19:29 (end). The end time is actually 19:30 minus one microsecond.

If we now have a key on the start time and this time is rastered we can block
overlapping reservations on the database level.

"""

from datetime import timedelta

# The raster values must divide an hour without any remaining minutes
VALID_RASTER_VALUES = (5, 10, 15, 30, 60)
MIN_RASTER_VALUE = min(VALID_RASTER_VALUES)
MAX_RASTER_VALUE = max(VALID_RASTER_VALUES)


def is_valid_raster(raster):
    return raster in VALID_RASTER_VALUES


def rasterize_start(date, raster):
    """Get a date and snap it to the beginning of the raster."""

    assert(is_valid_raster(raster))

    delta = timedelta(minutes=date.minute % raster,
                      seconds=date.second,
                      microseconds=date.microsecond)

    return date - delta


def rasterize_end(date, raster):
    """Get a date and snap it to the end of the raster. Note that
    the resulting time is the start of the next raster minus one microsecond.

    """
    if date.minute % raster:
        date = rasterize_start(date, raster)
        delta = timedelta(microseconds=-1, minutes=raster)
    else:
        delta = timedelta(microseconds=-1)
    return date + delta


def rasterize_span(start, end, raster):
    """Rasterizes both a start and an end date."""
    return rasterize_start(start, raster), rasterize_end(end, raster)


def iterate_span(start, end, raster):
    """Iterates through all raster blocks within a certain timespan."""
    start, end = rasterize_span(start, end, raster)

    step = start
    while (step <= end):
        yield step, step + timedelta(microseconds=-1, minutes=raster)
        step += timedelta(seconds=raster * 60)
