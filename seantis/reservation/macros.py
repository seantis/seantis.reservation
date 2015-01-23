from logging import getLogger
log = getLogger('seantis.reservation')

from five import grok
from zope.interface import Interface

from seantis.reservation import _
from seantis.reservation import settings
from seantis.reservation import utils
from seantis.reservation.base import BaseView
from seantis.reservation.form import ReservationDataView
from libres.db.models import Reservation
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

    def is_changeable_timespan(self, timespans, timespan):
        """ Returns True if the given bound timespan, a tuple including
        (start, end, token, id), may be changed by the time edit form.

        The list of timespans is passed as well because this information
        is around in in the reservation-timespans macro (where this is used)
        and because that allows for a much faster lookup.

        """
        if not hasattr(self, '_reservation_ids'):
            scheduler = self.context.scheduler()
            tokens = set(t.token for t in timespans)

            reservations = scheduler.change_reservation_time_candidates(tokens)
            reservations = reservations.with_entities(Reservation.id).all()

            if reservations:
                self._reservation_ids = set(r[0] for r in reservations)
            else:
                self._reservation_ids = set()

        return timespan.id in self._reservation_ids

    def build_your_reservations(
        self, reservations
    ):
        """ Prepares the given reservations to be shown in the
        your-reservations macro.

        """
        result = []

        for reservation in reservations:
            resource = utils.get_resource_by_uuid(reservation.resource)

            if resource is None:
                log.warn('Invalid UUID %s' % str(reservation.resource))
                continue

            resource = resource.getObject()

            data = {}

            data['token'] = reservation.token
            data['title'] = utils.get_resource_title(resource)

            timespans = []
            for start, end in reservation.timespans():
                timespans.append(utils.display_date(start, end))

            data['time'] = '<ul class="dense"><li>{}</li></ul>'.format(
                '</li><li>'.join(timespans)
            )
            data['quota'] = utils.get_reservation_quota_statement(
                reservation.quota
            ) if reservation.quota > 1 else u''

            data['url'] = resource.absolute_url()
            data['remove-url'] = ''.join((
                resource.absolute_url(),
                '/your-reservations?remove=',
                reservation.token.hex
            ))
            result.append(data)

        return result

    def build_allocations_table(
        self, allocations, start_time=None, end_time=None
    ):
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
                    utils.localize_date(start, time_only=True),
                    utils.localize_date(end, time_only=True),
                ))

        prev_date = None

        result = []

        tz = settings.timezone()

        for allocation in allocations:

            if start_time or end_time:
                s = start_time or allocation.display_start(tz).time()
                e = end_time or allocation.display_end(tz).time()

                s, e = allocation.limit_timespan(s, e)

                time_text = get_time_text(s, e)
            else:
                time_text = get_time_text(
                    allocation.display_start(tz), allocation.display_end(tz)
                )
                s, e = None, None

            availability, text, allocation_class = utils.event_availability(
                self.context, self.request, scheduler, allocation, s, e
            )

            date = ', '.join((
                self.translate(
                    self.short_days[allocation.display_start(tz).weekday()]
                ),
                utils.localize_date(
                    allocation.display_start(tz), long_format=False
                )
            ))

            result.append({
                'id': allocation.id,
                'group': allocation.group,
                'date': date,
                'time': time_text,
                'class': utils.event_class(availability),
                'is_first_of_date': prev_date != date,
                'text': ', '.join(text.split('\n')),
                'is_extra_result': getattr(
                    allocation, 'is_extra_result', False
                )
            })

            prev_date = date

        return result
