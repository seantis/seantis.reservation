import json
from datetime import date
from dateutil import rrule

from five import grok
from z3c.form import field
from z3c.form import button
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.browser.radio import RadioFieldWidget

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.interfaces import (
    IAllocation,
    IResourceAllocationDefaults,
    days
)
from seantis.reservation.form import (
    ResourceBaseForm,
    AllocationGroupView,
    extract_action_data,
)


class AllocationForm(ResourceBaseForm):
    grok.baseclass()
    hidden_fields = ['id', 'group', 'timeframes']


class AllocationAddForm(AllocationForm):
    permission = 'cmf.AddPortalContent'

    grok.name('allocate')
    grok.require(permission)

    context_buttons = ('allocate', )

    fields = field.Fields(IAllocation).select(
        'id', 'group', 'timeframes', 'whole_day', 'start_time', 'end_time',
        'recurring', 'day', 'recurrence_start', 'recurrence_end',
        'days', 'separately'
    )
    fields['days'].widgetFactory = CheckBoxFieldWidget
    fields['recurring'].widgetFactory = RadioFieldWidget

    label = _(u'Allocation')

    enable_form_tabbing = True
    default_fieldset_label = _(u'Date')

    @property
    def additionalSchemata(self):
        return [
            (
                'default', _(u'Settings'),
                field.Fields(IResourceAllocationDefaults).select(
                    'quota',
                    'reservation_quota_limit',
                    'approve',
                    'waitinglist_spots',
                    'partly_available',
                    'raster'
                )
            )
        ]

    def defaults(self):
        if self.start:
            weekday = self.start.weekday()
            daymap = dict([(d.value.weekday, d.value) for d in days])
            default_days = [daymap[weekday]]
        else:
            default_days = []

        recurrence_start, recurrence_end = self.default_recurrence()

        ctx = self.context
        return {
            'group': u'',
            'recurrence_start': recurrence_start,
            'recurrence_end': recurrence_end,
            'timeframes': self.json_timeframes(),
            'days': default_days,
            'quota': ctx.quota,
            'approve': ctx.approve,
            'waitinglist_spots': ctx.waitinglist_spots,
            'raster': ctx.raster,
            'partly_available': ctx.partly_available,
            'reservation_quota_limit': ctx.reservation_quota_limit
        }

    def timeframes(self):
        return self.context.timeframes()

    def json_timeframes(self):
        results = []
        for frame in self.timeframes():
            results.append(
                dict(title=frame.title, start=frame.start, end=frame.end)
            )

        dthandler = lambda obj: \
            obj.isoformat() if isinstance(obj, date) else None
        return unicode(json.dumps(results, default=dthandler))

    def default_recurrence(self):
        start = self.start and self.start.date() or None
        end = self.end and self.end.date() or None

        if not all((start, end)):
            return None, None

        for frame in sorted(self.timeframes(), key=lambda f: f.start):
            if frame.start <= start and start <= frame.end:
                return (frame.start, frame.end)

        return start, end

    def get_dates(self, data):
        """ Return a list with date tuples depending on the data entered by the
        user, using rrule if requested.

        """

        start, end = utils.get_date_range(
            data['day'], data['start_time'], data['end_time']
        )

        if not data['recurring']:
            return ((start, end))

        rule = rrule.rrule(
            rrule.DAILY,
            byweekday=data['days'],
            dtstart=data['recurrence_start'],
            until=data['recurrence_end'],
        )

        event = lambda d: \
            utils.get_date_range(d, data['start_time'], data['end_time'])

        return [event(d) for d in rule]

    @button.buttonAndHandler(_(u'Allocate'))
    @extract_action_data
    def allocate(self, data):
        dates = self.get_dates(data)

        def allocate():
            self.scheduler.allocate(
                dates,
                raster=data['raster'],
                quota=data['quota'],
                partly_available=data['partly_available'],
                grouped=not data['separately'],
                waitinglist_spots=data['waitinglist_spots'],
                approve=data['approve'],
                reservation_quota_limit=data['reservation_quota_limit'],
                whole_day=data['whole_day']

            )
            self.flash(_(u'Allocation added'))

        utils.handle_action(action=allocate, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class AllocationEditForm(AllocationForm):
    permission = 'cmf.ModifyPortalContent'

    grok.name('edit-allocation')
    grok.require(permission)

    context_buttons = ('edit', )

    fields = field.Fields(IAllocation).select(
        'id',
        'group',
        'whole_day',
        'start_time',
        'end_time',
        'day',
    )

    label = _(u'Edit allocation')

    enable_form_tabbing = True
    default_fieldset_label = _(u'Date')

    allocation_stale = False

    @property
    def additionalSchemata(self):
        return [
            (
                'default', _(u'Settings'),
                field.Fields(IResourceAllocationDefaults).select(
                    'quota',
                    'reservation_quota_limit',
                    'approve',
                    'waitinglist_spots'
                )
            )
        ]

    @property
    def allocation(self):
        if not self.id:
            return None
        else:
            return self.context.scheduler().allocation_by_id(self.id)

    def defaults(self):

        if not self.id or self.allocation_stale:
            return dict()

        allocation = self.allocation

        start, end = self.start, self.end
        if not all((start, end)):
            start = allocation.display_start
            end = allocation.display_end

        return {
            'id': self.id,
            'start_time': start.time(),
            'end_time': end.time(),
            'day': start.date(),
            'quota': allocation.quota,
            'approve': allocation.approve,
            'whole_day': allocation.whole_day,
            'waitinglist_spots': allocation.waitinglist_spots,
            'reservation_quota_limit': allocation.reservation_quota_limit
        }

    @button.buttonAndHandler(_(u'Edit'))
    @extract_action_data
    def edit(self, data):

        scheduler = self.context.scheduler()

        start, end = utils.get_date_range(
            data['day'], data['start_time'], data['end_time']
        )

        args = (
            data['id'],
            start,
            end,
            unicode(data['group'] or u''),
            data['quota'],
            data['waitinglist_spots'],
            data['approve'],
            data['reservation_quota_limit'],
            data['whole_day']
        )

        def edit():
            scheduler.move_allocation(*args)

            # ensure that the allocation is not accessed again by the defaults,
            # this prevents a DirtyReadOnlySession error
            self.allocation_stale = True

            self.flash(_(u'Allocation saved'))

        utils.handle_action(action=edit, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()


class AllocationRemoveForm(AllocationForm, AllocationGroupView):
    permission = 'cmf.ModifyPortalContent'

    grok.name('remove-allocation')
    grok.require(permission)

    context_buttons = ('delete', )

    fields = field.Fields(IAllocation).select('id', 'group')
    template = ViewPageTemplateFile('templates/remove_allocation.pt')

    label = _(u'Remove allocations')

    hidden_fields = ['id', 'group']
    ignore_requirements = True

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it.

        assert bool(data['id']) != bool(data['group']), \
            "Either id or group, not both"

        scheduler = self.scheduler

        def delete():
            scheduler.remove_allocation(id=data['id'], group=data['group'])
            self.flash(_(u'Allocation removed'))

        utils.handle_action(action=delete, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def defaults(self):
        return dict(id=self.id, group=self.group)
