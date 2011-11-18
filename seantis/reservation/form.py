from datetime import datetime, timedelta
from itertools import groupby

from five import grok
from plone.directives import form
from z3c.form import interfaces

from seantis.reservation import db
from seantis.reservation import utils
from seantis.reservation.models import Allocation
from seantis.reservation.interfaces import IResourceBase

def extract_action_data(fn):
    """ Decorator which inserted after a buttonAndHandler directive will
    put the extracted data into a named tuple for easier access. 

    """
    def wrapper(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        return fn(self, utils.dictionary_to_namedtuple(data))

    return wrapper

def from_timestamp(fn):
    """ Decorator which inserted after a property will convert the return value
    from a timestamp to datetime. 

    """
    def converter(self, *args, **kwargs):
        date = None
        try:
            date = fn(self, *args, **kwargs)
            return date and datetime.fromtimestamp(float(date)) or None
        except TypeError:
            return date

    return converter

class ResourceBaseForm(form.Form):
    """Baseform for all forms that work with resources as their context. 
    Provides helpful functions to all of them.

    """
    grok.baseclass()
    grok.context(IResourceBase)
    ignoreContext = True
    
    hidden_fields = ['id']
    ignore_requirements = False

    def updateWidgets(self):
        super(ResourceBaseForm, self).updateWidgets()

        # Hide fields found in self.hidden_fields
        for field in self.hidden_fields:
            if field in self.widgets:
                self.widgets[field].mode = interfaces.HIDDEN_MODE
        
        # Forces the wigets to completely ignore requirements 
        if self.ignore_requirements:
            self.widgets.hasRequiredFields = False

    def defaults(self):
        return {}

    def redirect_to_context(self):
        """ Redirect to the url of the resource. """
        self.request.response.redirect(self.context.absolute_url())

    @property
    def scheduler(self):
        """ Returns the scheduler of the resource. """
        return self.context.scheduler()

    @property
    @from_timestamp
    def start(self):
        if 'start' in self.request:
            return self.request['start']
        elif self.updateWidgets and 'start' in self.widgets:
            widget = self.widgets['start']
            if all(widget.day, widget.month, widget.year):
                return widget.value
            
        return None

    @property
    @from_timestamp
    def end(self):
        if 'end' in self.request:
            return self.request['end']
        elif self.updateWidgets and 'end' in self.widgets:
            widget = self.widgets['end']
            if all(widget.day, widget.month, widget.year):
                return widget.value
        
        return None

    @property
    def id(self):
        if 'id' in self.request:
            value = self.request['id']
        elif self.widgets and 'id' in self.widgets:
            value = self.widgets['id'].value
        else:
            return 0
        
        if value in (None, u'', ''):
            return 0
        else:
            return utils.request_id_as_int(value)

    @property
    def group(self):
        if 'group' in self.request:
            return unicode(self.request['group'].decode('utf-8'))
        elif self.widgets and 'group' in self.widgets:
            return unicode(self.widgets['group'].value)
        
        return u''

    def update(self, **kwargs):
        start, end = self.start, self.end
        if start and end:
            if 'day' in self.fields:
                self.fields['day'].field.default = start.date()
            if 'start_time' in self.fields:
                self.fields['start_time'].field.default = start.time()
            if 'end_time' in self.fields:
                self.fields['end_time'].field.default = end.time()
        
        other_defaults = self.defaults()
        for k, v in other_defaults.items():
            self.fields[k].field.default = v

        super(ResourceBaseForm, self).update(**kwargs)

class AllocationGroupView(object):
    """Combines functionality of different views which show groups 
    of allocations like in group.pt.

    The class with which it is used needs to offer the properties id and group
    and the context needs to be set to resource.

    Use the following macro to display:

    <metal:block use-macro="context/@@group/macros/grouplist" />

    """

    @utils.memoize
    def allocations(self):
        if self.group:
            query = self.context.scheduler().allocations_by_group(self.group)
            query = query.order_by(Allocation._start)
            return query.all()
        elif self.id:
            return [self.context.scheduler().allocation_by_id(self.id)]
        else:
            return []

    @utils.memoize
    def event_availability(self, allocation):
        return utils.event_availability(
                self.context,
                self.request,
                self.context.scheduler(),
                allocation
            )

    def event_class(self, allocation):
        base = 'fc-event fc-event-inner fc-event-skin groupListTime'
        return base  + ' ' + self.event_availability(allocation)[1]

    def event_title(self, allocation):
        return self.event_availability(allocation)[0]

class ReservationListView(object):
    """Combines functionality of different views which show reservations.

    The class with which it is used needs to provide the resource as context.

    The properties id and group must be implemented unless show_links is False

    The property reservation can be implemented if it is desired to only show
    one reservation.

    The property start and end can be implemented if it is desired to only
    show a subset of the reserved slots

    Use the following macro to display:

    <metal:block use-macro="context/@@reservations/macros/reservations" />

    """

    show_links = True

    @property
    def reservation(self):
        return None

    @property
    def highlight_group(self):
        query = self.build_query()
        if not query:
            return

        result = query.with_entities(Allocation.group).first()
        if not result:
            return

        return result[0]

    def reservation_info(self):
        return utils.random_name()

    def remove_all_url(self, reservation):
        base = self.context.absolute_url()
        return base + u'/remove-reservation?reservation=%s' % reservation[0]

    def remove_part_url(self, reservation):
        base = self.context.absolute_url()
        return base + u'/remove-reservation?reservation=%s&start=%s&end=%s' % (
                reservation[0], 
                utils.timestamp(reservation[2]), 
                utils.timestamp(reservation[3]+timedelta(microseconds=1))
            )

    def display_date(self, start, end):
        end += timedelta(microseconds=1)
        if start.date() == end.date():
            return start.strftime('%d.%m.%Y %H:%M - ') + end.strftime('%H:%M')
        else:
            return start.strftime('%d.%m.%Y %H:%M - ') \
                 + end.strftime('%d.%m.%Y %H:%M')

    def build_query(self):
        scheduler = self.context.scheduler()
        if self.reservation:
            return scheduler.reserved_slots_by_reservation(self.reservation)
        elif self.id:
            return scheduler.reserved_slots_by_allocation(self.id)
        elif self.group:
            return scheduler.reserved_slots_by_group(self.group)
        else:
            return None

    @utils.memoize
    def reservations(self):
        scheduler = self.context.scheduler()

        query = self.build_query()
        query = db.grouped_reservation_view(query)

        keyfn = lambda result: result.reservation
        
        def filter_slot(slot):
            allocation = scheduler.allocation_by_id(slot[1])
            return allocation.overlaps(self.start, self.end)

        if not hasattr(self, 'start') and not hasattr(self, 'end'):
            filter_slot = lambda slot: True
        elif not all((self.start, self.end)):
            filter_slot = lambda slot: True

        results = {}

        for key, values in groupby(query, key=keyfn):
            results[key] = [v for v in values if filter_slot(v)]

        return results
    