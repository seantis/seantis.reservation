import re

from z3c.form.converter import CalendarDataConverter
from z3c.form.converter import FormatterValidationError
from zope.i18n.format import DateTimeFormat
from zope.i18n.format import DateTimeParseError

from seantis.reservation import _


class FriendlyTimeDataConverter(CalendarDataConverter):
    """A special data converter for times.

    Tries to be very tolerant with different user input if the default
    converter fails.
    - Removes all characters that are not a digit and then parses the value.
      Thus it handles every input that contains at least three and at most four
      digits.
    - Auto-corrects user input for midnight when 24:xx is used as hour instead
      of 00:xx.

    """
    type = 'time'

    def __init__(self, field, widget):
        super(FriendlyTimeDataConverter, self).__init__(field, widget)

        # take extra care to only replace the hours, not the minutes
        self.pattern_24 = re.compile('[\D]*24[\D]*[\d]{2}[\D]*')
        self.pattern_non_digits = re.compile('\D')

        locale = self.widget.request.locale
        calendar = locale.dates.calendars['gregorian']
        self.friendly_formatter = DateTimeFormat('Hmm', calendar)

    def toFieldValue(self, value):
        try:
            return super(FriendlyTimeDataConverter, self).toFieldValue(value)
        except (FormatterValidationError, ValueError):
            try:
                if self.pattern_24.match(value):
                    value = value.replace('24', '00', 1)
                value = self.pattern_non_digits.sub('', value)
                return self.friendly_formatter.parse(value)
            except (DateTimeParseError, ValueError):
                msg = _('msg_error_time_value',
                        default=u'Please specify a valid time, '
                                 'for example 09:00')
                raise FormatterValidationError(msg, value)
