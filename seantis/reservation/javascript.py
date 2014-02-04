import json

from five import grok
from zope.interface import Interface
from plone.app.layout.viewlets.interfaces import IHtmlHead
from zope.component import getMultiAdapter

from seantis.reservation.base import BaseViewlet

TEMPLATE = u"""
<script type="text/javascript" class="javascript-settings">
    var %(name)s = %(variables)s;
</script>
"""


class JavascriptSettings(BaseViewlet):

    grok.context(Interface)
    grok.viewletmanager(IHtmlHead)

    @property
    def language(self):
        context = self.context.aq_inner
        portal_state = getMultiAdapter(
            (context, self.request), name=u'plone_portal_state'
        )
        return portal_state.language()

    @property
    def settings(self):
        return {
            'language': self.language
        }

    def render(self):
        return TEMPLATE % {
            'name': 'seantis_reservation_variables',
            'variables': json.dumps(self.settings)
        }
