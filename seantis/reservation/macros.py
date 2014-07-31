from five import grok
from plone import api
from zope.interface import Interface

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.base import BaseView
from seantis.reservation.form import ReservationDataView
from seantis.reservation.reserve import ReservationUrls


class View(BaseView, ReservationUrls, ReservationDataView):
    """A numer of macros for use with seantis.dir.base"""

    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('seantis-reservation-macros')

    template = grok.PageTemplateFile('templates/macros.pt')

    short_days = {
        0: _(u'MO'),
        1: _(u'TU'),
        2: _(u'WE'),
        3: _(u'TH'),
        4: _(u'FR'),
        5: _(u'SA'),
        6: _(u'SU')
    }

    def __getitem__(self, key):
        return self.template._template.macros[key]

    @property
    def utils(self):
        return utils

    def found_allocations(self, allocations, start_time=None, end_time=None):
        """ Prepares the given allocations for the found-allocations table.
        Only works on IResourceBase contexts.
        """

        if not allocations:
            return []

        scheduler = self.context.scheduler()
        whole_day_text = self.translate(_(u'Whole day'))

        def get_time_text(start, end):
            if utils.whole_day(start, end):
                return whole_day_text
            else:
                return ' - '.join((
                    api.portal.get_localized_time(start, time_only=True),
                    api.portal.get_localized_time(end, time_only=True),
                ))

        prev_date = None

        result = []

        for allocation in allocations:

            availability, text, allocation_class = utils.event_availability(
                self.context, self.request, scheduler, allocation
            )

            date = ', '.join((
                self.short_days[allocation.display_start.weekday()],
                api.portal.get_localized_time(
                    allocation.display_start, long_format=False
                )
            ))

            if start_time or end_time:
                s = start_time or allocation.display_start.time()
                e = end_time or allocation.display_end.time()

                s, e = allocation.limit_timespan(s, e)

                time_text = get_time_text(s, e)
            else:
                time_text = get_time_text(
                    allocation.display_start, allocation.display_end
                )

            result.append({
                'id': allocation.id,
                'date': date,
                'time': time_text,
                'class': utils.event_class(availability),
                'is_first_of_date': prev_date != date,
                'text': ', '.join(text.split('\n')),
            })

            prev_date = date

        return result
