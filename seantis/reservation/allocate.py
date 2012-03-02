import json
from datetime import date
from datetime import datetime
from dateutil import rrule

from five import grok
from z3c.form import field
from z3c.form import button
from z3c.form.ptcompat import ViewPageTemplateFile
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.browser.radio import RadioFieldWidget

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation import settings
from seantis.reservation.interfaces import IAllocation, days
from seantis.reservation.form import (
        ResourceBaseForm, 
        AllocationGroupView,
        extract_action_data,
    )

class AllocationForm(ResourceBaseForm):
    grok.baseclass()
    hidden_fields = ['id', 'group', 'timeframes']

    template = ViewPageTemplateFile('templates/allocate.pt')

    def update(self, **kwargs):
        
        # hide the waiting list setting if the reservations are not confirmed
        # manually by the user
        if settings.get('confirm_reservation'):
            self.hidden_fields = list(set(self.hidden_fields) - set(['waitinglist_spots']))
        else:
            self.hidden_fields.append('waitinglist_spots')
            self.hidden_fields = list(set(self.hidden_fields))

        super(AllocationForm, self).update(**kwargs)

class AllocationAddForm(AllocationForm):
    permission = 'cmf.ManagePortal'

    grok.name('allocate')
    grok.require(permission)
    
    fields = field.Fields(IAllocation)
    fields['days'].widgetFactory = CheckBoxFieldWidget
    fields['recurring'].widgetFactory = RadioFieldWidget

    label = _(u'Allocation')

    def defaults(self):        
        global days
        if self.start:
            weekday = self.start.weekday()
            daymap = dict([(d.value.weekday, d.value) for d in days])
            default_days = [daymap[weekday]]
        else:
            default_days = []
            
        recurrence_start, recurrence_end = self.default_recurrence()

        return {
            'quota': self.scheduler.quota,
            'group': u'',
            'recurrence_start': recurrence_start,
            'recurrence_end': recurrence_end,
            'timeframes': self.json_timeframes(),
            'days': default_days,
            'waitinglist_spots': self.scheduler.quota
        }

    def timeframes(self):
        return self.context.timeframes()

    def json_timeframes(self):
        results = []
        for frame in self.timeframes():
            results.append(
                    dict(title=frame.title, start=frame.start, end=frame.end)
                )

        dthandler = lambda obj: obj.isoformat() if isinstance(obj, date) else None
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

        start, end = utils.get_date_range(data.day, data.start_time, data.end_time)

        if not data.recurring:
            return ((start, end))

        rule = rrule.rrule(
                rrule.DAILY,
                byweekday=data.days,
                dtstart=data.recurrence_start, 
                until=data.recurrence_end,
            )
    
        event = lambda d:utils.get_date_range(d, data.start_time, data.end_time)
        
        return [event(d) for d in rule]

    @button.buttonAndHandler(_(u'Allocate'))
    @extract_action_data
    def allocate(self,data):
        dates = self.get_dates(data)

        action = lambda: self.scheduler.allocate(dates, 
                raster=data.raster,
                quota=data.quota,
                partly_available=data.partly_available,
                grouped= not data.separately,
                waitinglist_spots=data.waitinglist_spots
            )
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class AllocationEditForm(AllocationForm):
    permission = 'cmf.ManagePortal'

    grok.name('edit-allocation')
    grok.require(permission)

    fields = field.Fields(IAllocation).select(
            'id', 
            'group', 
            'start_time', 
            'end_time', 
            'day', 
            'quota', 
            'waitinglist_spots'
        )
    label = _(u'Edit allocation')

    @property
    def allocation(self):
        if not self.id:
            return None
        else:
            return self.context.scheduler().allocation_by_id(self.id)

    def update(self, **kwargs):
        """ Fills the defaults depending on the POST arguments given. """

        if not self.id:
            self.status = utils.translate(self.context, self.request, 
                    _(u'Invalid arguments')
                )
        else:
            allocation = self.allocation

            start, end = self.start, self.end
            if not all((start, end)):
                start = allocation.display_start
                end = allocation.display_end

            self.fields['id'].field.default = self.id
            self.fields['start_time'].field.default = start.time()
            self.fields['end_time'].field.default = end.time()
            self.fields['day'].field.default = start.date()
            self.fields['quota'].field.default = allocation.quota
            
            self.fields['waitinglist_spots'].field.default \
            = allocation.waitinglist_spots

        super(AllocationEditForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Edit'))
    @extract_action_data
    def edit(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        scheduler = self.context.scheduler()

        start, end = utils.get_date_range(data.day, data.start_time, data.end_time)
        
        args = (
            data.id, 
            start, 
            end, 
            unicode(data.group or u''), 
            data.quota, 
            data.waitinglist_spots
        )
        action = lambda: scheduler.move_allocation(*args)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

class AllocationRemoveForm(AllocationForm, AllocationGroupView):
    permission = 'cmf.ManagePortal'

    grok.name('remove-allocation')
    grok.require(permission)

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

        assert bool(data.id) != bool(data.group), "Either id or group, not both"

        scheduler = self.scheduler
        action = lambda: scheduler.remove_allocation(id=data.id, group=data.group)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @button.buttonAndHandler(_(u'Cancel'))
    def cancel(self, action):
        self.redirect_to_context()

    def update(self, **kwargs):
        if self.id or self.group:
            self.fields['id'].field.default = self.id
            self.fields['group'].field.default = self.group
        super(AllocationRemoveForm, self).update(**kwargs)