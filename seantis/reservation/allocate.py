from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import rrule

from five import grok
from plone.directives import form
from z3c.form import field
from z3c.form import button
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm
from zope import interface
from z3c.form.ptcompat import ViewPageTemplateFile
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from plone.memoize import view

from seantis.reservation import _
from seantis.reservation import error
from seantis.reservation import utils
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import VALID_RASTER_VALUES

from seantis.reservation.form import (
    ResourceBaseForm, 
    extract_action_data,
    from_timestamp
)

days = SimpleVocabulary(
        [SimpleTerm(value=rrule.MO, title=_(u'Monday')),
         SimpleTerm(value=rrule.TU, title=_(u'Tuesday')),
         SimpleTerm(value=rrule.WE, title=_(u'Wednesday')),
         SimpleTerm(value=rrule.TH, title=_(u'Thursday')),
         SimpleTerm(value=rrule.FR, title=_(u'Friday')),
         SimpleTerm(value=rrule.SA, title=_(u'Saturday')),
         SimpleTerm(value=rrule.SU, title=_(u'Sunday')),
        ]
    )
    
frequencies = SimpleVocabulary(
        [SimpleTerm(value=rrule.DAILY, title=_(u'Daily')),
         SimpleTerm(value=rrule.WEEKLY, title=_(u'Weekly')),
         SimpleTerm(value=rrule.MONTHLY, title=_(u'Monthly')),
         SimpleTerm(value=rrule.YEARLY, title=_(u'Yearly'))
        ]
    )

#TODO make defaults dynamic

class IAllocation(form.Schema):

    id = schema.Int(
        title=_(u'Id'),
        default=-1
        )

    start = schema.Datetime(
        title=_(u'From'),
        default=rasterize_start(datetime.today(), 60)
        )

    end = schema.Datetime(
        title=_(u'To'),
        default=rasterize_start(datetime.today(), 60) + timedelta(minutes=60)
        )

    partly_available = schema.Bool(
        title=_(u'Partly available'),
        default=False
        )

    raster = schema.Choice(
        title=_(u'Raster'),
        values=VALID_RASTER_VALUES,
        default=30
        )

    recurring = schema.Bool(
        title=_(u'Recurring'),
        default=False
        )

    frequency = schema.Choice(
        title=_(u'Frequency'),
        vocabulary=frequencies
        )

    days = schema.List(
        title=_(u'Days'),
        value_type=schema.Choice(vocabulary=days)
        )

    recurrence_end = schema.Date(
        title=_(u'Until'),
        default=date.today() + timedelta(days=30)
        )

    group = schema.Text(
        title=_(u'Group'),
        default=u'',
        max_length=100,
        required=False
        )

    quota = schema.Int(
        title=_(u'Quota'),
        )

    @interface.invariant
    def isValidDateRange(Allocation):
        if Allocation.start >= Allocation.end:
            raise interface.Invalid(_(u'End date before start date'))

    @interface.invariant
    def isValidGroup(Allocation):
        if Allocation.recurring and not Allocation.group:
            raise interface.Invalid(_(u'Recurring allocations require a group'))

    @interface.invariant
    def isValidQuota(Allocation):
        if not (0 <= Allocation.quota and Allocation.quota <= 100):
            raise interface.Invalid(_(u'Quota must be between 1 and 100'))

class AllocationForm(ResourceBaseForm):
    grok.baseclass()
    template = ViewPageTemplateFile('templates/allocate.pt')


class AllocationAddForm(AllocationForm):
    grok.name('allocate')
    grok.require('cmf.ManagePortal')
    
    fields = field.Fields(IAllocation)
    fields['days'].widgetFactory = CheckBoxFieldWidget

    label = _(u'Resource allocation')

    def defaults(self):
        return {'quota': self.scheduler.quota}

    def get_dates(self, data):
        """ Return a list with date tuples depending on the data entered by the
        user, using rrule if requested.

        """

        if not data.recurring:
            return ((data.start, data.end))

        # weekdays is only available for daily frequencies
        byweekday = data.frequency == rrule.DAILY and data.days or None
        
        rule = rrule.rrule(
                data.frequency,
                byweekday=byweekday,
                dtstart=data.start, 
                until=data.recurrence_end,
            )
    
        # the rule is created using the start date, the delta is added to each
        # generated date to get the end
        delta = data.end - data.start
        return [(d, d+delta) for d in rule]

    @button.buttonAndHandler(_(u'Allocate'))
    @extract_action_data
    def allocate(self,data):
        dates = self.get_dates(data)

        action = lambda: self.scheduler.allocate(dates, 
                raster=data.raster, 
                group=data.group,
                quota = data.quota,
                partly_available=data.partly_available
            )
        
        utils.handle_action(action=action, success=self.redirect_to_context)

class AllocationEditForm(AllocationForm):
    grok.name('edit-allocation')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocation).select('id', 'start', 'end', 'group', 'quota')
    label = _(u'Edit resource allocation')

    @property
    def id(self):
        return int(self.request.get('id', 0))

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

            group = allocation.group

            # hide the group if it's a uuid
            group = not utils.is_uuid(group) and group or None
            
            self.fields['id'].field.default = self.id
            self.fields['start'].field.default = start
            self.fields['end'].field.default = end
            self.fields['group'].field.default = group or u''
            self.fields['quota'].field.default = allocation.quota

        super(AllocationEditForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Edit'))
    @extract_action_data
    def edit(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        scheduler = self.context.scheduler()

        args = (data.id, data.start, data.end, unicode(data.group), data.quota)
        action = lambda: scheduler.move_allocation(*args)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

class AllocationRemoveForm(AllocationForm):
    grok.name('remove-allocation')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocation).select('id', 'group')
    template = ViewPageTemplateFile('templates/remove_allocation.pt')
    
    label = _(u'Remove resource allocation')

    hidden_fields = ['id', 'group']
    ignore_requirements = True

    @property
    def id(self):
        if self.widgets and 'id' in self.widgets:
            return int(self.widgets['id'].value)
        return int(self.request.get('id', 0))

    @property
    def group(self):
        if self.widgets and 'group' in self.widgets:
            return unicode(self.widgets['group'].value)
        return unicode(self.request.get('group', '').decode('utf-8'))

    @button.buttonAndHandler(_(u'Delete'))
    @extract_action_data
    def delete(self, data):

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        assert bool(data.id) != bool(data.group), "Either id or group, not both"

        scheduler = self.scheduler
        action = lambda: scheduler.remove_allocation(id=data.id, group=data.group)
        
        utils.handle_action(action=action, success=self.redirect_to_context)

    @view.memoize
    def allocations(self):
        if self.id:
            try:
                return [self.scheduler.allocation_by_id(self.id)]
            except error.NoResultFound:
                return []
        elif self.group:
            return self.scheduler.allocations_by_group(self.group).all()
        else:
            return []

    def update(self, **kwargs):
        if self.id or self.group:
            self.fields['id'].field.default = self.id
            self.fields['group'].field.default = self.group
        super(AllocationRemoveForm, self).update(**kwargs)

    @view.memoize
    def event_availability(self, allocation):
        return utils.event_availability(
                self.context,
                self.request,
                self.scheduler,
                allocation
            )

    def event_class(self, allocation):
        return self.event_availability(allocation)[1]

    def event_title(self, allocation):
        return self.event_availability(allocation)[0]