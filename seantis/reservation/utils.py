import re
import collections

from App.config import getConfiguration
from Acquisition import aq_inner
from zope.component import getMultiAdapter
from zope import i18n
from zope import interface
from Products.CMFCore.utils import getToolByName
from z3c.form.interfaces import ActionExecutionError

from seantis.reservation import _

def get_current_language(context, request):
    """Returns the current language"""
    context = aq_inner(context)
    portal_state = getMultiAdapter((context, request), name=u'plone_portal_state')
    return portal_state.language()

def translate(context, request, text):
    lang = get_current_language(context, request)
    return i18n.translate(text, target_language=lang)

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

def event_title(context, request, availability):
    if availability == 0:
        return translate(context, request, _(u'Occupied'))
    elif availability == 100:
        return translate(context, request, _(u'Free'))
    else:
        return translate(context, request, _(u'%i%% Free')) % availability

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