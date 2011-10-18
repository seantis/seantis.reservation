from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import rrule

from five import grok
from plone.directives import form
from z3c.form import field
from z3c.form import button
from z3c.form import interfaces
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm
from zope import interface
from z3c.saconfig import Session
from z3c.form.ptcompat import ViewPageTemplateFile
from plone.memoize import view

from seantis.reservation import _
from seantis.reservation import error
from seantis.reservation import utils
from seantis.reservation import resource
from seantis.reservation.raster import rasterize_start
from seantis.reservation.raster import VALID_RASTER_VALUES

frequencies = SimpleVocabulary(
        [SimpleTerm(value=rrule.DAILY, title=_(u'Daily')),
         SimpleTerm(value=rrule.WEEKLY, title=_(u'Weekly')),
         SimpleTerm(value=rrule.MONTHLY, title=_(u'Monthly')),
         SimpleTerm(value=rrule.YEARLY, title=_(u'Yearly'))
        ]
    )

#TODO make defaults dynamic

class IAllocation(interface.Interface):

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

    raster = schema.Choice(
        title=_(u'Raster'),
        values=VALID_RASTER_VALUES,
        default=60
        )

    recurring = schema.Bool(
        title=_(u'Recurring'),
        default=False
        )

    frequency = schema.Choice(
        title=_(u'Frequency'),
        vocabulary=frequencies
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

    @interface.invariant
    def isValidDateRange(Allocation):
        if Allocation.start >= Allocation.end:
            raise interface.Invalid(_(u'End date before start date'))

    @interface.invariant
    def isValidGroup(Allocation):
        if Allocation.recurring and not Allocation.group:
            raise interface.Invalid(_(u'Recurring allocations require a group'))

def from_timestamp(fn):
    def converter(self, *args, **kwargs):
        try:
            date = fn(self, *args, **kwargs)
            return date and datetime.fromtimestamp(float(date)) or None
        except TypeError:
            return None

    return converter

def handle_action(callback=None):
    try:
        if callback and callback() or True:
            Session.flush()
    except (error.OverlappingAllocationError,
            error.AffectedReservationError,
            error.ResourceLockedError), e:
        handle_exception(e)

def handle_exception(ex):
    msg = None
    if type(ex) == error.OverlappingAllocationError:
        msg = _(u'A conflicting allocation exists for the requested time period.')
    if type(ex) == error.AffectedReservationError:
        msg = _(u'An existing reservation would be affected by the requested change')
    if type(ex) == error.ResourceLockedError:
        msg = _(u'The resource is being edited by someone else. Please try again.')

    if not msg:
        raise NotImplementedError

    utils.form_error(msg)

class AllocationForm(form.Form):
    grok.context(resource.IResource)
    grok.name('allocate')
    grok.require('cmf.ManagePortal')

    template = ViewPageTemplateFile('templates/allocate.pt')

    fields = field.Fields(IAllocation)
    label = _(u'Resource allocation')

    ignoreContext = True

    @property
    @from_timestamp
    def start(self):
        return self.request.get('start')

    @property
    @from_timestamp
    def end(self):
        return self.request.get('end')

    @property
    def group(self):
        return unicode(self.request.get('group', '').decode('utf-8'))

    def update(self, **kwargs):
        start, end = self.start, self.end
        if start and end:
            self.fields['start'].field.default = start
            self.fields['end'].field.default = end

        super(AllocationForm, self).update(**kwargs)

    def updateWidgets(self):
        super(AllocationForm, self).updateWidgets()
        self.widgets['id'].mode = interfaces.HIDDEN_MODE

    @button.buttonAndHandler(_(u'Allocate'))
    def allocate(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start, end = data['start'], data['end']

        dates = []
        if not data['recurring']:
            dates.append((start, end))
        else:
            rule = rrule.rrule(
                    data['frequency'], 
                    dtstart=start, 
                    until=data['recurrence_end']
                )
        
            delta = end - start
            for date in rule:
                dates.append((date, date+delta))

        scheduler = self.context.scheduler

        group, raster = data['group'], data['raster']
        action = lambda: scheduler.allocate(dates, raster=raster, group=group)
        
        handle_action(callback=action)

        self.request.response.redirect(self.context.absolute_url())

class AllocationEditForm(AllocationForm):
    grok.context(resource.IResource)
    grok.name('edit-allocation')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocation).select('id', 'start', 'end', 'group')
    label = _(u'Edit resource allocation')

    ignoreContext = True

    @property
    def id(self):
        return int(self.request.get('id', 0))

    @property
    def allocation(self):
        if not self.id:
            return None
        else:
            return self.context.scheduler.allocation_by_id(self.id)

    def update(self, **kwargs):
        id = self.id

        if not id:
            self.status = utils.translate(self.context, self.request, 
                    _(u'Invalid arguments')
                )
        else:
            allocation = self.allocation
            group = allocation.group

            start, end = self.start, self.end
            if not all((start, end)):
                start = allocation.start
                end = allocation.end + timedelta(microseconds=1)

            if utils.is_uuid(group):
                group = None
            
            self.fields['id'].field.default = id
            self.fields['start'].field.default = start
            self.fields['end'].field.default = end
            self.fields['group'].field.default = group and group or u''

        super(AllocationEditForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Edit'))
    def edit(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorMessage
            return

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        scheduler = self.context.scheduler

        args = (data['id'], 
                data['start'], 
                data['end'], 
                unicode(data['group'] or ''))
        action = lambda: scheduler.move_allocation(*args)
        
        handle_action(callback=action)

        self.request.response.redirect(self.context.absolute_url())

class AllocationRemoveForm(form.Form):
    grok.context(resource.IResource)
    grok.name('remove-allocation')
    grok.require('cmf.ManagePortal')

    template = ViewPageTemplateFile('templates/remove_allocation.pt')

    fields = field.Fields(IAllocation).select('id', 'group')
    label = _(u'Remove resource allocation')

    ignoreContext = True

    @property
    def group(self):
        if self.widgets and 'group' in self.widgets:
            return unicode(self.widgets['group'].value)
        return unicode(self.request.get('group', '').decode('utf-8'))

    @property
    def id(self):
        if self.widgets and 'id' in self.widgets:
            return int(self.widgets['id'].value)
        return int(self.request.get('id', 0))

    @view.memoize
    def allocations(self):
        id, group = self.id, self.group
        if not id and not group:
            return []
        
        scheduler = self.context.scheduler

        if id:
            return [scheduler.allocation_by_id(id)]
        else:
            return scheduler.allocations_by_group(group).all()

    def updateWidgets(self):
        super(AllocationRemoveForm, self).updateWidgets()
        self.widgets['id'].mode = interfaces.HIDDEN_MODE
        self.widgets['group'].mode = interfaces.HIDDEN_MODE
        self.widgets.hasRequiredFields = False

    def update(self, **kwargs):
        if self.id or self.group:
            self.fields['id'].field.default = self.id
            self.fields['group'].field.default = self.group
        super(AllocationRemoveForm, self).update(**kwargs)

    def event_class(self, allocation):
        return utils.event_class(allocation.availability)

    def event_title(self, allocation):
        availability = allocation.availability
        return utils.event_title(self.context, self.request, availability)

    @button.buttonAndHandler(_(u'Delete'))
    def delete(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorMessage
            return

        # TODO since we can't trust the id here there should be another check
        # to make sure the user has the right to work with it. 

        id = data['id']
        group = data['group']

        assert(id or group)
        assert(not (id and group))

        scheduler = self.context.scheduler

        action = lambda: scheduler.remove_allocation(id=id, group=group)
        handle_action(callback=action)

        self.request.response.redirect(self.context.absolute_url())