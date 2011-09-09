from datetime import datetime
from dateutil.parser import parse as parseiso

from five import grok
from zope import schema
from zope.interface import Interface
from plone.directives import form
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import resource

class IAllocateForm(Interface):

    start = schema.Datetime(
        title=_(u'From')
        )

    end = schema.Datetime(
        title=_(u'To')
        )

class AllocateForm(form.Form):
    grok.context(resource.IResource)
    grok.name('reserve')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocateForm)

    label = _(u'Resource reservation')
    description = _(u'Reserve available dates on the resource')

    ignoreContext = True

    @button.buttonAndHandler(_(u'Reserve'))
    def allocate(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start = data['start']
        end = data['end']

        scheduler = self.context.scheduler
        scheduler.reserve(((start, end),))

        self.request.response.redirect(self.context.absolute_url())