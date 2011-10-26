import re
import collections

from App.config import getConfiguration
from Acquisition import aq_inner
from zope.component import getMultiAdapter
from zope import i18n
from zope import interface
from Products.CMFCore.utils import getToolByName
from z3c.form.interfaces import ActionExecutionError
from Products.statusmessages.interfaces import IStatusMessage
from seantis.reservation import error
from sqlalchemy.exc import DBAPIError

from seantis.reservation import _

def overlaps(start, end, otherstart, otherend):
    if otherstart <= start and start <= otherend:
        return True

    if start <= otherstart and otherstart <= end:
        return True

    return False

def get_current_language(context, request):
    """Returns the current language"""
    context = aq_inner(context)
    portal_state = getMultiAdapter((context, request), name=u'plone_portal_state')
    return portal_state.language()

def translate(context, request, text):
    lang = get_current_language(context, request)
    return i18n.translate(text, target_language=lang)

def form_info(message):
    def wrap(f):
        def info(self, *args):
            f(self, *args)
            if not self.status == self.formErrorsMessage:
                IStatusMessage(self.request).add(message, type='info')
        return info
    return wrap

def handle_action(action=None, success=None):
    try:
        if action: action()
        if success: success()

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
    
    count, availability = scheduler.availability(a.start, a.end)
    availability = availability // count

    if a.partly_available:
        if availability == 0:
            text = title(_(u'Occupied'))
        elif availability == 100:
            text = title(_(u'Free'))
        else:
            text = title(_(u'%i%% Free')) % availability
    else:
        spots = allocation.quota * availability // 100
        if spots:
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