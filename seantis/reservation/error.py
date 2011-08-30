class TimespanError(Exception):
    """Base exception for timespan related errors."""
    def __init__(self, timespan):
        self.timespan = timespan
    
    def __str__(self):
        return repr(self.timespan)

class AlreadyDefinedError(TimespanError):
    """Attempted to add an available timespan which overlaps another."""

class NotAvailableError(TimespanError):
    """Attempted to reserve a timespan which overlaps an alredy reserved one."""