import json

from datetime import datetime, timedelta
from collections import defaultdict
from itertools import groupby, ifilter
from functools import wraps

from five import grok
from plone.directives import form
from z3c.form import interfaces

from seantis.reservation import db
from seantis.reservation import utils
from seantis.reservation.models import Allocation, Reservation
from seantis.reservation.interfaces import IResourceBase

def extract_action_data(fn):
    """ Decorator which inserted after a buttonAndHandler directive will
    extract the data if possible or return before calling the decorated function

    """

    @wraps(fn)
    def wrapper(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        return fn(self, data)

    return wrapper

def from_timestamp(fn):
    """ Decorator which inserted after a property will convert the return value
    from a timestamp to datetime. 

    """

    @wraps(fn)
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
    
    disabled_fields = []
    hidden_fields = ['id', 'metadata']

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

        self.disableFields()

    def disableFields(self):
        # Disable fields
        for field in self.disabled_fields:
            if field in self.widgets:
                self.widgets[field].disabled = 'disabled'

        # Disabled fields are not submitted later, so we store the values
        # of the widgets in a hidden field, using the metadata field
        # which must exist for this to work
        if self.disabled_fields:
            assert 'metadata' in self.widgets

            metadata = dict()
            for field in self.disabled_fields:
                if field in self.widgets:
                    metadata[field] = self.widgets[field].value

            self.widgets['metadata'].value = json.dumps(metadata)

    def get_data(self, data, key):
        """ Return the key of the given data dictionary, 
        consulting the metadata dictionary.

        """
        metadata = self.metadata(data)
        if metadata and key in metadata:
            return metadata.get(key)

        return data.get(key)

    def defaults(self):
        return {}

    def redirect_to_context(self):
        """ Redirect to the url of the resource. """
        self.request.response.redirect(self.context.absolute_url())

    @property
    def scheduler(self):
        """ Returns the scheduler of the resource. """
        return self.context.scheduler()

    def metadata(self, data):
        metadata = data.get('metadata')
        if metadata:
            return json.loads(metadata)
        return dict()

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

    def flash(self, message, type='info'):
        utils.flash(self.context, message, type)

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

        # call plone.autoform if it is used as a mixin in a child-class
        if hasattr(self, 'updateFields'):
            self.updateFields()

        super(ResourceBaseForm, self).update(**kwargs)

        self.disableFields()

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
        """ Returns the group id to highlight when hovering over any result.
        As there is no reservation view with multiple groups, only one result
        can be returned. 

        """
        return hasattr(self, 'group') and self.group or u''

    def reservation_info(self, token):
        """ Returns the registration information to be printed
        on the header of the reservation. 

        """

        if token in self.pending_reservations():
            return self.pending_reservations()[token][0].title

        if token in self.approved_reservations():
            return self.approved_reservations()[token][0].title

        return u''

    def extended_info(self, token):
        """ Returns the extended info dictionary to be printed in the detail view. """

        if token in self.pending_reservations():
            return self.pending_reservations()[token][0].data

        if token in self.approved_reservations():
            return self.approved_reservations()[token][0].data

        return dict()

    def sorted_info_keys(self, token):
        data = self.extended_info(token)
        items = [(d[0], d[1]['values'][0]['sortkey']) for d in data.items()]

        return [i[0] for i in sorted(items, key=lambda k: k[1])]

    def sorted_values(self, values):
        return sorted(values, key=lambda v: v['sortkey'])

    def display_date(self, start, end):
        """ Formates the date range given for display. """
        end += timedelta(microseconds=1)
        if start.date() == end.date():
            return start.strftime('%d.%m.%Y %H:%M - ') + end.strftime('%H:%M')
        else:
            return start.strftime('%d.%m.%Y %H:%M - ') \
                 + end.strftime('%d.%m.%Y %H:%M')

    def reservations(self, status):
        """ Returns all reservations relevant to this list in a dictionary
        keyed by reservation token. 

        """
        scheduler = self.context.scheduler()
        if self.reservation:
            query = scheduler.reservations_by_token(self.reservation)
        elif self.id:
            query = scheduler.reservations_by_allocation(self.id)
        elif self.group:
            query = scheduler.reservations_by_group(self.group)
        else:
            return {}

        query = query.filter(Reservation.status == status)
        query.order_by(Reservation.id)

        reservations = utils.OrderedDict()
        for r in query.all():
            if r.token in reservations:
                reservations[r.token].append(r)
            else:
                reservations[r.token] = [r]

        return reservations

    @utils.memoize
    def pending_reservations(self):
        """ Returns a dictionary of reservations, keyed by reservation uid. """

        return self.reservations(status=u'pending')

    @utils.memoize
    def approved_reservations(self):
        """ Returns a dictionary of reservations, keyed by reservation uid. """

        return self.reservations(status=u'approved')