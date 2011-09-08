from five import grok
from plone.directives import form
from plone.dexterity.content import Container
from zope import schema

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
    pass

class View(grok.View):
    grok.context(IResourceBase)
    grok.require('zope2.View')
    
    #template = grok.PageTemplateFile('templates/resource.pt')

    def render(self, **kwargs):
        return 'Hello World'