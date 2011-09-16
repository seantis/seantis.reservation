class ReservationError(Exception):
    pass

class OverlappingAllocationError(ReservationError):

    def __init__(self, start, end, existing):
        self.start = start
        self.end = end
        self.existing = existing

class ResourceLockedError(ReservationError):
    pass

class AffectedReservationError(ReservationError):

    def __init__(self, existing):
        self.existing = existing