import re
import collections
from uuid import UUID

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
        return 0
        
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

def handle_action(action=None, success=None, message_handler=None):
    try:
        result = None
        if action: result = action()
        if success: success()

        return result

    except Exception, e:
        e = hasattr(e, 'orig') and e.orig or e
        handle_exception(e, message_handler)

def form_error(msg):
    raise ActionExecutionError(interface.Invalid(msg))

def handle_exception(ex, message_handler=form_error):
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
        msg =_(u'Invalid change. Your request may have already been processed earlier.')
    if type(ex) == error.NotReservableError:
        msg =_(u'No reservable slot found.')
    if type(ex) == error.ReservationTooLong:
        msg =_(u"Reservations can't be made for more than 24 hours at a time")
    if type(ex) == error.ThrottleBlock:
        msg =_(u'Too many reservations in a short time. Wait for a moment before trying again.')

    if not msg:
        raise ex

    message_handler(msg)

def is_uuid(obj):
    if isinstance(obj, basestring):

        regex = re.compile(
            '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
        )

        return re.match(regex, unicode(obj))
    
    return isinstance(obj, UUID)

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

# obsolete in python 2.7
def total_timedelta_seconds(td):
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6