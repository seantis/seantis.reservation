from five import grok
from zope.interface import Interface


class View(grok.View):
    """A numer of macros for use with seantis.dir.base"""

    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('seantis-reservation-macros')

    template = grok.PageTemplateFile('templates/macros.pt')

    def __getitem__(self, key):
        return self.template._template.macros[key]
