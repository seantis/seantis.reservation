import json

from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from plone.uuid.interfaces import IUUID
from zope import schema

from seantis.reservation import Scheduler
from seantis.reservation import _

class IResourceBase(form.Schema):

    title = schema.TextLine(
            title=_(u'Name')
        )

    description = schema.Text(
            title=_(u'Description'),
            required=False
        )


class IResource(IResourceBase):
    pass


class Resource(Container):

    @property
    def uuid(self):
        return IUUID(self)

    @property
    def scheduler(self):
        return Scheduler(self.uuid)


class View(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    
    template = grok.PageTemplateFile('templates/resource.pt')

    calendar_id = 'seantis-reservation-calendar'

    @property
    def calendar_js(self):
        template = """
        <script type="text/javascript">
            (function($) {
                $(document).ready(function() {
                    $('#%s').fullCalendar(%s);
                });
            })( jQuery );
        </script>
        """

        eventurl = self.context.absolute_url_path() + '/slots'
        options = json.dumps(dict(events=eventurl))

        return template % (self.calendar_id, options)

class Slots(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    grok.name('slots')

    def render(self, **kwargs):
        pass
        