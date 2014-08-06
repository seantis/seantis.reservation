from itertools import groupby
from seantis.reservation.models.reservation import BoundTimespan


class CombinedReservations(object):

    __slots__ = ['reservation', 'combined_timespans']

    def __init__(self, first_reservation, timespans):
        self.reservation = first_reservation
        self.combined_timespans = timespans

    def timespans(self):
        return [(t[0], t[1]) for t in self.combined_timespans]

    def bound_timespans(self):
        return self.combined_timespans

    def __getattr__(self, key):
        return getattr(self.reservation, key)


def combine_reservations(reservations):
    """ Takes a list of reservations, groups them by token and iterates
    through them, creating reservation record like objects which reference
    the first data found in the list of reservations and all the timespans
    combined.

    seantis.reservation assumes that a reservation with one token and many
    different reservations uses the same reservation data on all records
    linked by this token. This is less flexible, but a lot easier to
    explain and understand by the user.

    For example, take these reservations:

    id - token - data - start - end
    01 - 0xabc - x: 1 - 01.01 - 02.01
    02 - 0xabc - x: 1 - 02.01 - 03.01

    Fed into this class they iteration yields this result as
    a MinimalReservation:

    reservation {
        token     => '0xabc',
        data      => x: 1
        timespans => [(01.01, 02.01, 0xabc, 01), (02.01, 03.01, 0xabc, 02)]
    }

    It's really all about grouping reservations in a way that makes the
    result transparently usable by the reservation list view.
    """

    by_token = lambda r: r.token
    reservations = sorted(reservations, key=by_token)

    for token, reservations in groupby(reservations, key=by_token):
        reservations = tuple(r for r in reservations)

        timespans = []
        for reservation in reservations:
            for start, end in reservation.timespans():
                timespans.append(
                    BoundTimespan(
                        start, end, reservation.token, reservation.id
                    )
                )

        yield CombinedReservations(
            first_reservation=reservations[0], timespans=timespans
        )
