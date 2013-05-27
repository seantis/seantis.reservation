import json
from datetime import date
from dateutil import rrule

from five import grok
from z3c.form import field
from z3c.form import button
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.interfaces import (
    IAllocation,
    IResourceAllocationDefaults
)
from seantis.reservation.form import (
    ResourceBaseForm,
    AllocationGroupView,
    extract_action_data,
)
from plone.formwidget.recurrence.z3cform.widget import RecurrenceFieldWidget
from plone.formwidget.datetime.z3cform.widget import DateFieldWidget
from z3c.form.interfaces import ActionExecutionError
from zope.interface import Invalid
from zope import schema
import itertools


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
        'day', 'recurrence', 'separately',
    )

    fields['day'].widgetFactory = DateFieldWidget
    fields['recurrence'].widgetFactory = RecurrenceFieldWidget

    label = _(u'Allocation')

    enable_form_tabbing = True
    default_fieldset_label = _(u'Date')

    def updateWidgets(self):
        super(AllocationAddForm, self).updateWidgets()
        widget = self.widgets['recurrence']
        widget.start_field = 'day'
        widget.show_repeat_forever = False

    @property
    def additionalSchemata(self):
        return [
            (
                'default', _(u'Advanced Settings'),
                field.Fields(IResourceAllocationDefaults).select(
                    'quota',
                    'reservation_quota_limit',
                    'approve_manually',
                    'partly_available',
                    'raster'
                )
            )
        ]

    @property
    def whole_day(self):
        if not self.start:
            return False

        return all((
            (self.start.hour, self.start.minute) == (0, 0),
            (self.end.hour, self.end.minute) == (0, 0)
        ))

    def defaults(self):
        ctx = self.context
        return {
            'group': u'',
            'timeframes': self.json_timeframes(),
            'quota': ctx.quota,
            'approve_manually': ctx.approve_manually,
            'raster': ctx.raster,
            'partly_available': ctx.partly_available,
            'reservation_quota_limit': ctx.reservation_quota_limit,
            'whole_day': self.whole_day
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

    def get_dates(self, data):
        """ Return a list with date tuples depending on the data entered by the
        user, using rrule if requested.

        """

        start, end = utils.get_date_range(
            data['day'], data['start_time'], data['end_time']
        )

        if not data['recurrence']:
            return ((start, end))

        rule = rrule.rrulestr(data['recurrence'],
                              dtstart=start)

        event = lambda d: \
            utils.get_date_range(d, data['start_time'], data['end_time'])

        return [event(d) for d in rule]

    @button.buttonAndHandler(_(u'Allocate'))
    @extract_action_data
    def allocate(self, data):
        self._validate_recurrence_options(data)
        dates = self.get_dates(data)

        def allocate():
            self.scheduler.allocate(
                dates,
                raster=data['raster'],
                quota=data['quota'],
                partly_available=data['partly_available'],
                grouped=not data['separately'],
                approve_manually=data['approve_manually'],
                reservation_quota_limit=data['reservation_quota_limit'],
                whole_day=data['whole_day'],
                rrule=data['recurrence'],

            )
            self.flash(_(u'Allocation added'))

        utils.handle_action(action=allocate, success=self.redirect_to_context)

    def _validate_recurrence_options(self, data):
        """Validate that when recurrence is configured and the resource is
        partly available the separately option must be enabled as well.

        This validation has been moved here from a form invariant since
        invariants do not seem to work with groups.

        """
        if 'recurrence' in data and data['recurrence']:
            if data['partly_available'] and not data['separately']:
                raise ActionExecutionError(Invalid(_(
                          u'Partly available allocations can only be reserved '
                          u'separately'
                          )))

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
                    'approve_manually'
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
            'approve_manually': allocation.approve_manually,
            'whole_day': allocation.whole_day,
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
            data['approve_manually'],
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

    destructive_buttons = ('delete', )

    fields = field.Fields(IAllocation).select('id', 'group') + \
                            field.Fields(schema.Int(__name__='recurrence_id'))
    template = ViewPageTemplateFile('templates/remove_allocation.pt')

    label = _(u'Remove allocations')

    hidden_fields = ['id', 'group', 'recurrence_id']
    ignore_requirements = True

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):
        nof_params = len(list(itertools.ifilter(None, (
                                                data['id'],
                                                data['group'],
                                                data['recurrence_id'],)
                         )))
        assert nof_params == 1, "Exactly one of id, group or recurrence_id"

        scheduler = self.scheduler

        def delete():
            scheduler.remove_allocation(id=data['id'],
                                        group=data['group'],
                                        recurrence_id=data['recurrence_id'])
            self.flash(_(u'Allocation removed'))

        utils.handle_action(action=delete, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def defaults(self):
        id, group, recurrence_id = self.id, self.group, self.recurrence_id
        result = dict(id=None, recurrence_id=None, group=None)
        if recurrence_id:
            result['recurrence_id'] = recurrence_id
        elif group:
            result['group'] = group
        elif id:
            result['id'] = id
        return result
