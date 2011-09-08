from five import grok
from plone.directives import form
from plone.dexterity.content import Container

class IResourceBase(form.Schema):
    pass


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