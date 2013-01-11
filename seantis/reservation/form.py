import json

from datetime import datetime
from functools import wraps

from five import grok
from plone.directives import form
from z3c.form import interfaces
from z3c.form import field
from z3c.form.group import GroupForm

from seantis.reservation import _
from seantis.reservation import utils
from seantis.reservation.models import Allocation, Reservation
from seantis.reservation.interfaces import IResourceBase

from plone.memoize import view

from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from plone.z3cform.fieldsets import utils as z3cutils


def extract_action_data(fn):
    """ Decorator which inserted after a buttonAndHandler directive will
    extract the data if possible or return before calling the decorated
    function.

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
            return date and datetime.utcfromtimestamp(float(date)) or None
        except TypeError:
            return date

    return converter


class ResourceBaseForm(GroupForm, form.Form):
    """Baseform for all forms that work with resources as their context.
    Provides helpful functions to all of them.

    """
    grok.baseclass()
    grok.context(IResourceBase)

    ignoreContext = True
    ignore_requirements = False

    disabled_fields = []
    hidden_fields = ['id', 'metadata']

    context_buttons = tuple()

    css_class = 'seantis-reservation-form wizard'

    template = ViewPageTemplateFile('templates/form.pt')

    def updateWidgets(self):
        super(ResourceBaseForm, self).updateWidgets()

        # Hide fields found in self.hidden_fields
        for f in self.hidden_fields:
            if f in self.widgets:
                self.widgets[f].mode = interfaces.HIDDEN_MODE

        # Forces the wigets to completely ignore requirements
        if self.ignore_requirements:
            self.widgets.hasRequiredFields = False

        self.disableFields()

    def disableFields(self):

        # Disable fields
        for f in self.disabled_fields:
            if f in self.widgets:
                self.widgets[f].disabled = 'disabled'

        # Disabled fields are not submitted later, so we store the values
        # of the widgets in a hidden field, using the metadata field
        # which must exist for this to work
        if self.disabled_fields:
            assert 'metadata' in self.widgets

            metadata = dict()
            for f in self.disabled_fields:
                if f in self.widgets:
                    metadata[f] = self.widgets[f].value

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
    @utils.memoize
    def scheduler(self):
        """ Returns the scheduler of the resource. """
        language = utils.get_current_language(self.context, self.request)
        return self.context.scheduler(language=language)

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

    def updateFields(self):
        self.form.groups = []

        if not hasattr(self, 'additionalSchemata'):
            return

        for prefix, group, schema in self.additionalSchemata:
            fields = field.Fields(schema, prefix=prefix)

            if hasattr(self, 'customize_fields'):
                self.customize_fields(fields)

            z3cutils.add(self.form, fields, group=group)

    def updateActions(self):
        super(ResourceBaseForm, self).updateActions()

        for button in self.context_buttons:
            self.actions[button].addClass("context")

    def update(self, **kwargs):
        self.updateFields()

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
        return base + ' ' + self.event_availability(allocation)[1]

    def event_title(self, allocation):
        return self.event_availability(allocation)[0]


class ReservationDataView(object):
    """Mixin for reservation-data showing."""

    def sorted_info_keys(self, data):
        items = [(d[0], d[1]['values'][0]['sortkey']) for d in data.items()]

        return [i[0] for i in sorted(items, key=lambda k: k[1])]

    def sorted_values(self, values):
        return sorted(values, key=lambda v: v['sortkey'])

    def display_info(self, value):
        """ Transforms json data values into a human readable format
        where appropriate.

        """

        if value is True:
            return _(u'Yes')

        if value is False:
            return _(u'No')

        if isinstance(value, basestring):
            return utils.decode_for_display(value)

        return value


class ResourceParameterView(object):
    """Mixin for views that accept a list of uuids for resources."""

    @property
    @view.memoize
    def uuids(self):
        uuids = self.request.get('uuid', [])

        if not hasattr(uuids, '__iter__'):
            uuids = [uuids]

        return uuids

    @property
    @view.memoize
    def resources(self):
        objs = dict()

        for uuid in self.uuids:
            try:
                objs[uuid] = utils.get_resource_by_uuid(uuid) \
                    .getObject()
            except AttributeError:
                continue

        return objs


class ReservationListView(ReservationDataView):
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
        return hasattr(self, 'group') and utils.string_uuid(self.group) or u''

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
        """ Returns the extended info dictionary to be printed in the detail
        view.
        """

        if token in self.pending_reservations():
            return self.pending_reservations()[token][0].data

        if token in self.approved_reservations():
            return self.approved_reservations()[token][0].data

        return dict()

    def display_date(self, start, end):
        return utils.display_date(start, end)  # kept here for use in template

    def all_reservations(self):
        scheduler = self.context.scheduler()

        if self.reservation:
            return scheduler.reservations_by_token(self.reservation)
        if self.id:
            return scheduler.reservations_by_allocation(self.id)
        if self.group:
            return scheduler.reservations_by_group(self.group)

        return None

    def reservations(self, status):
        """ Returns all reservations relevant to this list in a dictionary
        keyed by reservation token.

        """
        query = self.all_reservations()

        if not query:
            return {}

        query = query.filter(Reservation.status == status)
        query = query.filter(Reservation.session_id == None)
        query.order_by(Reservation.id)

        reservations = utils.OrderedDict()
        for r in query.all():
            if r.token in reservations:
                reservations[r.token].append(r)
            else:
                reservations[r.token] = [r]

        return reservations

    @utils.cached_property
    def uncommitted_reservations_count(self):
        query = self.all_reservations()
        query = query.filter(Reservation.session_id != None)

        return query.count()

    @property
    def uncommitted_reservations(self):
        count = self.uncommitted_reservations_count

        if not count:
            return u''

        if count == 1:
            return _(
                u'There is one reservation being entered for this resource.'
            )            

        return _(
            u'There are ${nb} reservations being entered for this resource.',
            mapping={'nb': self.uncommitted_reservations_count}
        )

    @utils.memoize
    def pending_reservations(self):
        """ Returns a dictionary of reservations, keyed by reservation uid. """

        return self.reservations(status=u'pending')

    @utils.memoize
    def approved_reservations(self):
        """ Returns a dictionary of reservations, keyed by reservation uid. """

        return self.reservations(status=u'approved')
