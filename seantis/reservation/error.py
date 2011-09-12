class ReservationError(Exception):
    pass

class OverlappingAllocationError(ReservationError):

    def __init__(self, start, end, existing):
        self.start = start
        self.end = end
        self.existing = existing

class ResourceLockedError(ReservationError):
    pass