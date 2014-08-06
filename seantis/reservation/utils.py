import re
import time
import json
import collections
import functools
import isodate
import base64
import sys

from copy import deepcopy
from datetime import datetime, timedelta, date, time as datetime_time
from urlparse import urljoin
from urllib import quote
from itertools import tee, izip
from uuid import UUID
from uuid import uuid5 as new_uuid_mirror
from plone.uuid.interfaces import IUUID, IUUIDAware
from plone import api

import pytz

from plone.dexterity.utils import SchemaNameEncoder

from App.config import getConfiguration
from Acquisition import aq_inner
from zope.component import getMultiAdapter
from zope.component.hooks import getSite
from zope import i18n
from zope import interface
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.i18nl10n import weekdayname_msgid_abbr, monthname_msgid
from z3c.form.interfaces import ActionExecutionError
from plone.i18n.locales.languages import _languagelist
from plone.app.textfield.value import RichTextValue

from OFS.interfaces import IApplication
from Products.CMFPlone.interfaces import IPloneSiteRoot

from seantis.reservation import error
from seantis.reservation import _


# avoid circular import of settings
_settings = None


def settings():
    global _settings

    if _settings is None:
        from seantis.reservation import settings
        _settings = settings

    return _settings


try:
    from collections import OrderedDict  # python >= 2.7
    OrderedDict  # Pyflakes
except ImportError:
    from ordereddict import OrderedDict  # python < 2.7
    OrderedDict  # Pyflakes

dexterity_encoder = SchemaNameEncoder()


class ConfigurationError(Exception):
    pass


def maybe_call(value):
    return value() if callable(value) else value


def profile(fn):
    """ Naive profiling of a function.. on unix systems only. """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.time()

        result = fn(*args, **kwargs)
        print fn.__name__, 'took', (time.time() - start) * 1000, 'ms'

        return result

    return wrapper


def additional_data_dictionary(data, fti):
    """ Takes the data from a post request and puts the relevant bits into
    a dictionary with the following structure:

    {
        "form_key": {
            "desc": "Form Description",
            "interface": "The interface used",
            "values": [
                {
                    "key": "value_key",
                    "sortkey": 1-n,
                    "value": "value",
                    "desc": "Value Description"
                },
                ...
            ]
        }
    }

    Interfaces used in the reservation data are the interfaces with the
    IReservationFormSet marker set.

    The dictionary is later converted to JSON and stored on the reservation.
    """

    result = dict()
    used_data = dict([(k, v) for k, v in data.items() if v is not None])

    def values(iface, ifacekey):
        for key, value in used_data.items():
            if not key.startswith(ifacekey + '.'):
                continue

            subkey = key.split('.')[1]
            desc = iface.getDescriptionFor(subkey).title
            sortkey = iface.get(subkey).order

            yield dict(key=subkey, desc=desc, value=value, sortkey=sortkey)

    for key, info in fti.items():
        desc, iface = info[0], info[1]

        record = dict()
        record['desc'] = desc
        record['interface'] = iface.getName()
        record['values'] = list(values(iface, key))

        if not record['values']:
            continue

        result[key] = record

    return result


def merge_data_dictionaries(base, extra):
    """ Merges the given data dictionaries. The extra dictionary will overwrite
    matching keys in the base dictionary.

    """

    merged = deepcopy(base)

    for extra_form in extra:
        if extra_form in base:
            merged[extra_form]['desc'] = extra[extra_form]['desc']
            merged[extra_form]['interface'] = extra[extra_form]['interface']

            # this really should be a dict, since the key matters...
            base_values = dict(
                (i['key'], i) for i in base[extra_form]['values']
            )
            extra_values = dict(
                (i['key'], i) for i in extra[extra_form]['values']
            )

            merged[extra_form]['values'] = []

            for value in base[extra_form]['values']:
                if value['key'] in extra_values:
                    merged[extra_form]['values'].append(
                        extra_values[value['key']]
                    )
                else:
                    merged[extra_form]['values'].append(
                        base_values[value['key']]
                    )

            for value in extra[extra_form]['values']:
                if value['key'] in base_values:
                    continue
                else:
                    merged[extra_form]['values'].append(value)
        else:
            merged[extra_form] = extra[extra_form]

    return merged


def additional_data_objects(data):
    """ Takes the additional data dictionary and returns a new dictionary
    with the keys being the formsets, and the values being objects.

    An 'address' formset with 'street' and 'town' will produce this:

    {'address': obj}

    Where obj can be acccessed like this:

    obj.street
    obj.town

    """
    result = {}

    class DynamicObject(object):
        pass

    for formset in data:
        obj = DynamicObject()
        for item in data[formset]['values']:
            setattr(obj, item['key'], item['value'])

        result[formset] = obj

    return result


def zope_root():
    this = getSite()

    while not IApplication.providedBy(this):
        this = this.aq_inner.aq_parent

    return this


def plone_sites(root=None):
    root = root or zope_root()

    sites = []
    for id, item in root.items():
        if not IPloneSiteRoot.providedBy(item):
            continue

        sites.append(item)
        sites.extend(plone_sites(item))

    return sites


def mock_data_dictionary(data, formset_key='mock', formset_desc='Mocktest'):
    """ Given a dictionary of key values this function returns a dictionary
    with the same structure as additional_data_dictionary, without the use
    of interfaces.

    This function exists for testing purposes.
    """

    records = list()

    formset = dict()
    formset['desc'] = formset_desc
    formset['interface'] = 'mockinterface'
    formset['values'] = records

    for i, item in enumerate(data.items()):
        records.append(
            dict(key=item[0], sortkey=i, value=item[1], desc=item[0])
        )

    return {formset_key: formset}


def count_overlaps(dates, start, end):
    count = 0

    for otherstart, otherend in dates:
        count += overlaps(start, end, otherstart, otherend) and 1 or 0

    return count


def overlaps(start, end, otherstart, otherend):
    if otherstart <= start and start <= otherend:
        return True

    if start <= otherstart and otherstart <= end:
        return True

    return False

_requestid_expr = re.compile(r'\d')


def request_id_as_int(string):
    """Returns the id of a request as int without throwing an error if invalid
    characters are in the requested string (like ?id=11.11).

    """
    if string is None:
        return 0

    return int(''.join(re.findall(_requestid_expr, string)))


class memoize(object):
    """Decorator that caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned, and
    not re-evaluated.
    """
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            self.cache[args] = value
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            # Better to not cache than to blow up entirely.
            return self.func(*args)

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


@memoize
def _exposure():
    # keep direct imports out of utils as it will lead to circular imports
    from seantis.reservation import exposure
    return exposure


def compare_link(resources):
    """Builds the compare link for the given list of resources. """

    # limit the resources already on the link, as the view needs
    # at least two visible resources to be even callable
    # (another check for security is made in the resources module later)
    resources = _exposure().limit_resources(resources)

    if len(resources) < 2:
        return ''

    link = resources[0:1][0].absolute_url_path() + '?'
    compare_to = [string_uuid(r) for r in resources[1:]]

    for uuid in compare_to:
        link += 'compare_to=' + string_uuid(uuid) + '&'

    return link.rstrip('&')


def export_link(context, request, resources):
    """Builds the reservations excel export link for the
    given list of resources.

    """

    if not resources:
        return ''

    if not _exposure().for_views(context, request)('reservation-exports'):
        return ''

    return ''.join((
        context.absolute_url(),
        '/reservation-exports?uuid=',
        '&uuid='.join(
            map(string_uuid, resources)
        )
    ))


def monthly_report_link(context, request, resources):
    """Builds the monthly report link given the list of the resources
    using the current year and month."""

    if not resources:
        return ''

    # ensure that the view may be called
    if not _exposure().for_views(context, request)('monthly_report'):
        return ''

    today = datetime.now()

    url = context.absolute_url()

    # note that 'monthly_report' is copied in reports.py
    url += '/monthly_report'
    url += '?year=' + str(today.year)
    url += '&month=' + str(today.month)

    for resource in resources:
        url += '&uuid=' + string_uuid(resource)

    return url


def latest_reservations_link(context, request, resources):
    """Builds the latest reservations report link. """
    if not resources:
        return ''

    # ensure that the view may be called
    if not _exposure().for_views(context, request)('latest_reservations'):
        return ''

    return '{}/{}?uuid={}'.format(
        context.absolute_url(), 'latest_reservations',
        '&uuid='.join(map(string_uuid, resources))
    )


def get_current_language(context, request):
    """Returns the current language of the request"""
    context = aq_inner(context)
    portal_state = getMultiAdapter(
        (context, request), name=u'plone_portal_state'
    )
    return portal_state.language()


def get_current_site_language():
    """Returns the current language of the current site"""

    context = getSite()
    portal_languages = getToolByName(context, 'portal_languages')
    langs = portal_languages.getSupportedLanguages()

    return langs and langs[0] or u'en'


def get_site_email_sender():
    """Returns the default sender of emails of the current site in the
    following format: 'sendername<sender@domain>'.

    """

    site = getSite()
    address = site.getProperty('email_from_address')
    name = site.getProperty('email_from_name')

    if not address:
        return None

    if name:
        return '%s<%s>' % (name, address)
    else:
        return address


def translator(context, request):
    """Returns a function which takes a single string and translates it using
    the curried values for context & request.

    """
    def curried(text):
        return translate(context, request, text)
    return curried


def translate(context, request, text, domain=None):
    """Translates the given text using context & request."""

    # xx-xx languages will not work here, though they work when Plone does
    # it in a template. For now it does not matter as we have no country
    # specific translation available
    lang = get_current_language(context, request).split('-')[0]
    return i18n.translate(text, target_language=lang, domain=domain)


def translate_workflow(context, request, text):
    return translate(context, request, text, domain='plone')


def native_language_name(code):
    return _languagelist[code]['native']


def handle_action(action=None, success=None, message_handler=None):
    """Calls 'action' and then 'success' if everything went well or
    'message_handler' with a message if an exception happened.

    If no message_handler is given, an ActionExecutionError is raised
    with the message attached.

    """
    try:
        result = None
        if action:
            result = action()
        if success:
            success()

        return result

    except Exception, e:
        e = hasattr(e, 'orig') and e.orig or e
        handle_exception(e, sys.exc_info(), message_handler)


def form_error(msg):
    raise ActionExecutionError(interface.Invalid(msg))


def handle_exception(ex, exception_info, message_handler=None):
    if isinstance(ex, error.CustomReservationError):
        form_error(ex.msg)

    msg = error.errormap.get(type(ex))

    if not msg:
        raise exception_info[1], None, exception_info[2]

    if message_handler:
        message_handler(msg)
    else:
        form_error(msg)

_uuid_regex = re.compile(
    '[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}'
)


def is_uuid(obj):
    """Returns true if the given obj is a uuid. The obj may be a string
    or of type UUID. If it's a string, the uuid is checked with a regex.
    """
    if isinstance(obj, basestring):
        return re.match(_uuid_regex, unicode(obj))

    return isinstance(obj, UUID)


def string_uuid(obj):
    """ Returns the uuid as string without hyphens. Takes either UUIDs, strings
    with hyphens, objects which are IUUIDAware or objects which have a UID
    attribute. (The latter works for catalog brains). """

    if isinstance(obj, basestring):
        obj = str(obj)
    elif hasattr(obj, 'UID'):
        if callable(obj.UID):
            obj = obj.UID()  # plone 4.3, because
        else:
            obj = obj.UID
    elif IUUIDAware.providedBy(obj):
        obj = IUUID(obj)
    elif callable(obj):
        obj = obj()

    return UUID(str(obj)).hex


def real_uuid(obj):
    """ Same as string_uuid but casted to uuid.UUID. """
    return UUID(string_uuid(obj))


# TODO cache this incrementally
def generate_uuids(uuid, quota):
    mirror = lambda n: new_uuid_mirror(uuid, str(n))
    return [mirror(n) for n in xrange(1, quota)]


def uuid_query(uuid):
    """ Returns a tuple of uuids for querying the zodb. See why:
    http://stackoverflow.com/questions/10137632/
    querying-portal-catalog-using-typed-uuids-instead-of-string-uuids

    """

    uuid = string_uuid(uuid)

    if '-' in uuid:
        return (uuid.replace('-', ''), uuid)
    return (uuid, '-'.join([
        uuid[:8], uuid[8:12], uuid[12:16], uuid[16:20], uuid[20:]]))


def get_resource_by_uuid(
    uuid, ensure_portal_type='seantis.reservation.resource'
):
    """Returns the zodb object with the given uuid."""
    catalog = getToolByName(getSite(), 'portal_catalog')

    if ensure_portal_type:
        results = catalog(UID=uuid_query(uuid), portal_type=ensure_portal_type)
    else:
        results = catalog(UID=uuid_query(uuid))

    return len(results) == 1 and results[0] or None


def get_resource_title(resource, title_prefix=''):
    if hasattr(resource, '__parent__'):
        parent = resource.__parent__.title
    elif hasattr(resource, 'parent'):
        parent = resource.parent().title
    else:
        return title_prefix + resource.title

    return ' - '.join((parent, title_prefix + resource.title))


def get_reservation_quota_statement(quota):
    if quota > 1:
        return _(u'<b>${quota}</b> reservations', mapping={'quota': quota})
    else:
        return _(u'<b>1</b> reservation')


class UUIDEncoder(json.JSONEncoder):
    """Encodes UUID objects as string in JSON."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return string_uuid(obj)
        return json.JSONEncoder.default(self, obj)


class UserFormDataEncoder(json.JSONEncoder):
    """Encodes additional user data."""

    def default(self, obj):

        if isinstance(obj, set):
            return list(obj)

        if isinstance(obj, datetime):
            return u'__datetime__@%s' % isodate.datetime_isoformat(obj)

        if isinstance(obj, date):
            return u'__date__@%s' % isodate.date_isoformat(obj)

        if isinstance(obj, datetime_time):
            return u'__time__@%s' % isodate.time_isoformat(obj)

        if isinstance(obj, RichTextValue):
            return u'__richtext__@%s' % base64.b64encode(json.dumps(dict(
                raw=obj.raw,
                encoding=obj.encoding,
                mime=obj.mimeType,
                output_mime=obj.outputMimeType
            )))

        return json.JSONEncoder.default(self, obj)


def userformdata_decode(string):
    if not isinstance(string, basestring):
        return string

    if string.startswith(u'__date__@'):
        return isodate.parse_date(string[9:19])

    if string.startswith(u'__datetime__@'):
        return isodate.parse_datetime(string[13:32])

    if string.startswith(u'__time__@'):
        return isodate.parse_time(string[9:18])

    if string.startswith(u'__richtext__@'):
        data = json.loads(base64.b64decode(string[13:]))
        return RichTextValue(
            raw=data['raw'],
            mimeType=data['mime'],
            outputMimeType=data['output_mime'],
            encoding=data['encoding']
        )

    return string


def as_human_readable_string(value):
    if isinstance(value, basestring):
        return value

    if isinstance(value, datetime):
        # don't use strftime here because users may end up entering year '3'
        # strftime does not suppport years before 1900, which is just lame
        # in this case we just use the German locale for now..
        if value.year < 1900:
            return '%02d.%02d.%04d %02d:%02d' % (
                value.day,
                value.month,
                value.year,
                value.hour,
                value.minute
            )
        else:
            return api.portal.get_localized_time(value, long_format=True)

    if isinstance(value, date):
        if value.year < 1900:
            return '%02d.%02d.%04d' % (
                value.day,
                value.month,
                value.year
            )
        else:
            dt = datetime(value.year, value.month, value.day)
            return api.portal.get_localized_time(dt, long_format=False)

    if isinstance(value, RichTextValue):
        return value.output

    if value is True:
        return _(u'Yes')

    if value is False:
        return _(u'No')

    if value is None:
        return u''

    if isinstance(value, (list, tuple)):
        return ', '.join(as_human_readable_string(v) for v in value)

    return value


def event_class(availability):
    """Returns the event class to be used depending on the availability."""

    s = settings()

    available = s.get('available_threshold')
    partly = s.get('partly_available_threshold')

    if availability >= available:
        return 'event-available'
    elif partly <= availability and availability < available:
        return 'event-partly-available'
    else:
        return 'event-unavailable'


def allocation_class(allocation):
    """Returns the class set on the fullcalendar event for the allocation."""
    if allocation.approve_manually:
        return 'approve-manually'
    else:
        return 'approve-automatically'


def event_availability(
    context, request, scheduler, allocation, start=None, end=None
):
    """ Returns the availability, the text with the availability and the class
    for the availability to display on the calendar view.

    If start and end are given and the allocation is partly_available
    the availability is set to 100% if the scheduler's find_spot method
    returns True. That is if the timespan between start and end
    is completely reservable.

    This is very involved and slow, so you probably shouldn't use that.
    This feature tries to account for the fact that parts of allocations
    can be reserved in search, where the user gets the impression that
    the time he entered is the actual allocation, when that timespan might
    only refer to a part of the allocation.

    For now this will be a new features which we'll test against. In the
    future this needs to be made much faster => TODO.

    """
    translate = translator(context, request)

    if start and end and allocation.partly_available:
        availability = scheduler.find_spot(allocation, start, end) and 100 or 0
    else:
        availability = scheduler.availability(allocation.start, allocation.end)

    spots = int(round(allocation.quota * availability / 100))

    # get the title shown on the calendar block
    if allocation.partly_available:
        text = translate(_(u'%i%% Free')) % availability
    else:
        if allocation.quota > 1:
            text = translate(_(u'%i/%i Spots Available')) % (
                spots, allocation.quota
            )
        else:
            text = translate(_(u'%i/%i Spot Available')) % (
                spots, allocation.quota
            )

    # with approval the number of people in the waitinglist have to be shown
    if allocation.approve_manually:
        length = allocation.waitinglist_length
        if length == 0:
            text += '\n' + translate(_(u'Waitinglist is Free'))
        elif length == 1:
            text += '\n' + translate(_(u'One Person Waiting'))
        else:
            text += '\n' + translate(_(u'%i People Waiting')) % length

    return (
        availability,
        text,
        ' '.join((event_class(availability), allocation_class(allocation)))
    )


def flatten(l):
    """Generator for flattening irregularly nested lists. 'Borrowed' from here:

    http://stackoverflow.com/questions/2158395/
    flatten-an-irregular-list-of-lists-in-python
    """
    for el in l:
        if isinstance(el, collections.Iterable) and \
                not isinstance(el, basestring):
            for sub in flatten(el):
                yield sub
        else:
            yield el


def pack(v):
    """Puts v in a list if not already an iterator."""
    return [v] if not hasattr(v, '__iter__') else v


def pairs(l):
    """Takes any list and returns pairs:
    ((a,b),(c,d)) => ((a,b),(c,d))
    (a,b,c,d) => ((a,b),(c,d))

    http://opensourcehacker.com/2011/02/23/
    tuplifying-a-list-or-pairs-in-python/
    """
    l = list(flatten(l))
    return zip(*[l[x::2] for x in (0, 1)])


def pairwise(iterable):
    """Almost like pairs, but not quite:
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    """
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)


def safe_parse_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_config(key):
    config = getConfiguration()
    if not hasattr(config, 'product_config'):
        raise ConfigurationError('No configuration found.')

    configuration = config.product_config.get('seantis.reservation', dict())
    return configuration.get(key)


# obsolete in python 2.7
def total_timedelta_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10 ** 6) / \
        10 ** 6


def utc_mktime(utc_tuple):
    """Returns number of seconds elapsed since epoch

    Note that no timezone are taken into consideration.

    utc tuple must be: (year, month, day, hour, minute, second)

    """

    if len(utc_tuple) == 6:
        utc_tuple += (0, 0, 0)
    return time.mktime(utc_tuple) - time.mktime((1970, 1, 1, 0, 0, 0, 0, 0, 0))


def utctimestamp(dt):
    dt = dt.replace(tzinfo=pytz.utc)
    return utc_mktime(dt.timetuple())


def utcnow():
    """Returns the utc now function result with the correct timezone set. """
    return datetime.utcnow().replace(tzinfo=pytz.utc)


def merge_reserved_slots(slots):
    """Given a list of reserved slots a list of tuples with from-to datetimes
    is formed, with adjacent slots being combined into one continious timespan.
    Usually this leaves reserved_slots be, but if the slots in the list come
    from a partially available allocation the reserved_slots of such an
    allocation can be merged into one timespan.

    So instead of
    08:00 - 08:14:59:59
    08:15 - 08:29:59:59

    You'll get
    08:00 - 08:30

    for this, the display_start and display_end of ResourceSlot are used."""

    class Timespan(object):
        def __init__(self, start, end):
            self.start = start
            self.end = end

    if len(slots) == 1:
        return [Timespan(slots[0].start, slots[0].end)]

    slots = sorted(slots, key=lambda s: s.start)

    merged = []
    current = Timespan(None, None)

    for this, next in pairwise(slots):

        if abs((next.start - this.end).seconds) <= 1:
            current.start = current.start and current.start or this.start
            current.end = next.end
        else:
            merged.append(current)
            current = Timespan(None, None)

    if current.start:
        merged.append(current)

    return merged


def urlparam(base, url, params):
    """Joins an url, adding parameters as query parameters."""
    if not base.endswith('/'):
        base += '/'

    urlquote = lambda fragment: quote(unicode(fragment).encode('utf-8'))
    querypair = lambda pair: pair[0] + '=' + urlquote(pair[1])

    query = '?' + '&'.join(map(querypair, params.items()))
    return ''.join(reduce(urljoin, (base, url, query)))


class EventUrls(object):
    def __init__(self, resource, request, exposure):
        self.resource = resource
        self.base = resource.absolute_url_path()
        self.request = request
        self.translate = translator(resource, request)
        self.menu = {}
        self.order = []
        self.exposure = exposure
        self.default = ""
        self.move = ""

    @memoize
    def restricted_url(self, view):
        """Returns a function which can be used to build an url with optional
        parameters. The function only builds the url if the current user has
        the right to do so.

        """
        base = self.resource.absolute_url_path()
        is_exposed = self.exposure.for_views(self.resource, self.request)

        def build(params):
            if is_exposed(view):
                return urlparam(base, view, params)
            else:
                return None

        # return closure
        return build

    @memoize
    def get_restricted(self, view, params):
        urlfactory = self.restricted_url(view)
        if not urlfactory:
            return None

        return urlfactory(params)

    def menu_add(self, group, name, view, params, target):
        url = self.get_restricted(view, params)
        if not url:
            return

        group = self.translate(group)
        name = self.translate(name)

        if not group in self.menu:
            self.menu[group] = []
            self.order.append(group)

        self.menu[group].append(dict(name=name, url=url, target=target))

    def default_url(self, view, params):
        url = self.get_restricted(view, params)
        if not url:
            return

        self.default = url

    def move_url(self, view, params):
        url = self.get_restricted(view, params)
        if not url:
            return

        self.move = url


def get_date_range(day, start_time, end_time):
    """Returns the date-range of a date a start and an end time."""
    start = datetime.combine(day, start_time)
    end = datetime.combine(day, end_time)

    # since the user can only one date with separate times it is assumed
    # that an end before a start is meant for the following day
    if end < start:
        end += timedelta(days=1)

    return start, end


def flash(context, message, type='info'):
    context.plone_utils.addPortalMessage(message, type)


def month_name(context, request, month):
    """Returns the text for the given month (1-12)."""
    assert (1 <= month and month <= 12)
    msgid = monthname_msgid(month)
    return translate(context, request, msgid, 'plonelocales')


def weekdayname_abbr(context, request, day):
    """Returns the text for the given day (0-6), 0 being sunday.
    Since 0 is sunday in the plone function and monday in the python stdlib
    you might want to shift the day.weekday() result"""
    assert (0 <= day and day <= 6)
    msgid = weekdayname_msgid_abbr(day)
    return translate(context, request, msgid, 'plonelocales')


def shift_day(stdday):
    return abs(0 - (stdday + 1) % 7)


def whole_day(start, end):
    """Returns true if the given start, end range should be considered
    a whole-day range. This is so if the start time is 0:00:00 and the end
    time either 0:59:59 or 0:00:00 and if there is at least a diff
    erence of 23h 59m 59s / 86399 seconds between them.

    This is relevant for the calendar-display for now. This might very well be
    replaced again in the future when we introduce timezones.

    """

    assert start <= end, "The end needs to be equal or greater than the start"

    if isinstance(start, datetime_time):
        start = datetime(2000, 1, 1, start.hour, start.minute, start.second)

    if isinstance(end, datetime_time):
        end = datetime(2000, 1, 1, end.hour, end.minute, end.second)

    if (start.hour, start.minute, start.second) != (0, 0, 0):
        return False

    if (end.hour, end.minute, end.second) not in ((0, 0, 0), (23, 59, 59)):
        return False

    if (end - start).total_seconds() < 86399:
        return False

    return True


def context_path(context):
    """Returns the physical path for brains and objects alike."""

    if hasattr(context, 'getPath'):
        return context.getPath().split('/')  # same as getPhysicalPath
    else:
        return context.getPhysicalPath()


def portal_type_in_site(portal_type):
    catalog = getToolByName(getSite(), 'portal_catalog')
    results = catalog(portal_type=portal_type)

    return results


def portal_type_in_context(context, portal_type, depth=1):
    """Returns the given portal types _within_ the current context."""

    path = '/'.join(context_path(context))

    catalog = getToolByName(context, 'portal_catalog')
    results = catalog(
        portal_type=portal_type,
        path={'query': path, 'depth': depth}
    )
    return results


def portal_type_by_context(context, portal_type):
    """Returns the given portal_type _for_ the current context. Portal types
    for a context are required by traversing up the acquisition context.

    """

    # As this code is used for backend stuff that needs to be callable for
    # every user the idea is to do an unrestricted traverse.

    # Calling unrestrictedTraverse first seems to work with the supposedly
    # restricted catalog.

    path = context_path(context)
    context = context.aq_inner.unrestrictedTraverse(path)

    def traverse(context, portal_type):
        frames = portal_type_in_context(context, portal_type)
        if frames:
            return [f.getObject() for f in frames]
        else:
            if not hasattr(context, 'portal_type'):
                return []
            if context.portal_type == 'Plone Site':
                return []

            parent = context.aq_inner.aq_parent
            return traverse(parent, portal_type)

    return traverse(context, portal_type)


def align_date_to_day(date, direction):
    """ Aligns the given date to the beginning or end of the day, depending on
    the direction.

    E.g.
    2012-1-24 10:00 down -> 2012-1-24 00:00
    2012-1-24 10:00 up   -> 2012-1-24 23:59:59'999999

    """
    assert direction in ('up', 'down')

    aligned = (0, 0, 0, 0) if direction == 'down' else (23, 59, 59, 999999)

    if (date.hour, date.minute, date.second, date.microsecond) == aligned:
        return date

    if direction == 'down':
        return date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return date + timedelta(days=1, microseconds=-1)


def align_range_to_day(start, end):
    assert start <= end, "{} - {} is an invalid range".format(start, end)

    return align_date_to_day(start, 'down'), align_date_to_day(end, 'up')


def display_date(start, end):
    """ Formates the date range given for display. """

    if end.microsecond != 999999:
        end -= timedelta(microseconds=1)

    if (start, end) == align_range_to_day(start, end):
        if start.date() == end.date():
            return api.portal.get_localized_time(start, long_format=False)
        else:
            return ' - '.join((
                api.portal.get_localized_time(start, long_format=False),
                api.portal.get_localized_time(end, long_format=False)
            ))

    end += timedelta(microseconds=1)

    if start.date() == end.date():
        return ' - '.join((
            api.portal.get_localized_time(start, long_format=True),
            api.portal.get_localized_time(end, time_only=True)
        ))
    else:
        return ' - '.join((
            api.portal.get_localized_time(start, long_format=True),
            api.portal.get_localized_time(end, long_format=True)
        ))


class United(object):
    """ Puts items added through 'append' into the same group as the last
    item which was appended, as long as the matchfn which is passed the last
    and the current item returns true.

    e.g.

    united = United(lambda last, current: last == current)

    united.append(1)
    -> united.groups => [[1]]

    united.append(1)
    -> united.groups => [[1, 1]]

    united.append(2)
    -> united.groups => [[1, 1], [2]]

    united.append(1)
    -> united.groups => [[1, 1], [2], [1]]

    """

    def __init__(self, matchfn):
        self.matchfn = matchfn
        self.groups = []
        self.new_group()

    def new_group(self):
        self.groups.append([])

    @property
    def current_group(self):
        return self.groups[-1]

    def append(self, item):
        if not self.current_group:
            self.current_group.append(item)
        else:
            if not self.matchfn(self.current_group[-1], item):
                self.new_group()

            self.current_group.append(item)


def unite(iterator, matchfn):
    """ Iterates through the given records and groups the records if two
    records passed to the match function result in True.

    e.g.

    unite([1, 1, 1, 2, 2], lambda last, current: last == current)

    -> [[1, 1, 1], [2, 2]]

    Note that for this to work the records need to be sorted, not unlike
    when using the collection's group function. See 'United' doc above to
    learn why.
    """

    united = United(matchfn)

    for item in iterator:
        united.append(item)

    return united.groups


def unite_dates(dates):
    """ Takes a list of start / end date tuples and compacts it by merging
    dates which can be considered an unbroken range.

    So given a list like this:

        [
            (01.01.2012 00:00, 02.01.2012 00:00),
            (02.01.2012 00:00, 03.01.2012 00:00),
            (05.01.2012 00:00, 06.01.2012 00:00)
        ]

    (Where the dates are actually datetime instances)

    We should get this result:

        [
            (01.01.2012 00:00, 03.01.2012 00:00),
            (05.01.2012 00:00, 06.01.2012 00:00)
        ]

    """
    sorted_dates = sorted(dates, key=lambda pair: pair[0])
    for group in unite(sorted_dates, lambda this, next: this[1] == next[0]):
        yield group[0][0], group[-1][1]


class cached_property(object):
    """A read-only @property that is only evaluated once. The value is cached
    on the object itself rather than the function or class; this should prevent
    memory leakage."""

    def __init__(self, fget, doc=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = fget.__name__
        self.__module__ = fget.__module__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result
