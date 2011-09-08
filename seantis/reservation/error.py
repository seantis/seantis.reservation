class ReservationError(Exception):
    pass

class OverlappingAvailable(ReservationError):

    def __init__(self, start, end, existing):
        self.start = start
        self.end = end
        self.existing = existing