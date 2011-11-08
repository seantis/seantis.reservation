import re
import collections

from App.config import getConfiguration
from Acquisition import aq_inner
from zope.component import getMultiAdapter
from zope import i18n
from zope import interface
from Products.CMFCore.utils import getToolByName
from z3c.form.interfaces import ActionExecutionError
from seantis.reservation import error
from collections import namedtuple

from seantis.reservation import _

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
    if string == None:
        return -1
        
    return int(''.join(re.findall(_requestid_expr, string)))

def compare_link(resources):
    if len(resources) < 2:
            return ''

    link = resources[0:1][0].absolute_url_path() + '?'
    compare_to = [r.uuid() for r in resources[1:]]

    for uuid in compare_to:
        link += 'compare_to=' + str(uuid) + '&'
        
    return link.rstrip('&')

def dictionary_to_namedtuple(dictionary):
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

def get_current_language(context, request):
    """Returns the current language"""
    context = aq_inner(context)
    portal_state = getMultiAdapter((context, request), name=u'plone_portal_state')
    return portal_state.language()

def translate(context, request, text):
    lang = get_current_language(context, request)
    return i18n.translate(text, target_language=lang)

def handle_action(action=None, success=None):
    try:
        result = None
        if action: result = action()
        if success: success()

        return result

    except Exception, e:
        e = hasattr(e, 'orig') and e.orig or e
        handle_exception(e)

def handle_exception(ex):
    msg = None
    if type(ex) == error.OverlappingAllocationError:
        msg = _(u'A conflicting allocation exists for the requested time period.')
    if type(ex) == error.AffectedReservationError:
        msg = _(u'An existing reservation would be affected by the requested change')
    if type(ex) == error.TransactionRollbackError:
        msg = _(u'The resource is being edited by someone else. Please try again.')
    if type(ex) == error.NoResultFound:
        msg = _(u'The item does no longer exist.')
    if type(ex) == error.AlreadyReservedError:
        msg = _(u'The requested period is no longer available.')
    if type(ex) == error.IntegrityError:
        msg =_(u'This record already exists.')
    if type(ex) == error.NotReservableError:
        msg =_(u'No reservable slot found.')

    if not msg:
        raise ex

    form_error(msg)

def form_error(msg):
    raise ActionExecutionError(interface.Invalid(msg))

def is_uuid(text):
    regex = re.compile(
            '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
        )

    return re.match(regex, unicode(text))

def get_resource_by_uuid(context, uuid):
    catalog = getToolByName(context, 'portal_catalog')
    results = catalog(UID=uuid)
    return len(results) == 1 and results[0] or None

def event_class(availability):
    if availability == 0:
        return 'event-unavailable'
    elif availability == 100:
        return 'event-available'
    else:
        return 'event-partly-available'

def event_availability(context, request, scheduler, allocation):
    a = allocation
    title = lambda msg: translate(context, request, msg)
    
    availability = scheduler.availability(a.start, a.end)

    if a.partly_available:
        if availability == 0:
            text = title(_(u'Occupied'))
        elif availability == 100:
            text = title(_(u'Free'))
        else:
            text = title(_(u'%i%% Free')) % availability
    else:
        spots = int(round(allocation.quota * availability / 100))
        if spots:
            if spots == 1:
                text = title(_(u'1 Spot Available'))
            else:
                text = title(_(u'%i Spots Available')) % spots
        else:
            text = title(_(u'No spots available'))

    return text, event_class(availability)

def flatten(l):
    """Generator for flattening irregularly nested lists. 'Borrowed' from here:
    
    http://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists-in-python
    """
    for el in l:
        if isinstance(el, collections.Iterable) and not isinstance(el, basestring):
            for sub in flatten(el):
                yield sub
        else:
            yield el

def pairs(l):
    """Takes any list and returns pairs:
    ((a,b),(c,d)) => ((a,b),(c,d))
    (a,b,c,d) => ((a,b),(c,d))
    
    http://opensourcehacker.com/2011/02/23/tuplifying-a-list-or-pairs-in-python/
    """
    l = list(flatten(l))
    return zip(*[l[x::2] for x in (0,1)])

def get_config(key):
    config = getConfiguration()
    configuration = config.product_config.get('seantis.reservation', dict())
    return configuration.get(key)

class cached_property(object):
    '''A read-only @property that is only evaluated once. The value is cached
    on the object itself rather than the function or class; this should prevent
    memory leakage.'''
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