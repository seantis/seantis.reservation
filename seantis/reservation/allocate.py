from five import grok
from zope import schema
from zope.interface import Interface
from plone.directives import form
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import raster
from seantis.reservation import resource

class IAllocateForm(Interface):

    start = schema.Datetime(
        title=_(u'From')
        )

    end = schema.Datetime(
        title=_(u'To')
        )

    raster = schema.Choice(
        title=_(u'Raster'),
        values=raster.VALID_RASTER_VALUES
        )

class AllocateForm(form.Form):
    grok.context(resource.IResource)
    grok.name('allocate')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IAllocateForm)

    label = _(u'Resource allocation')
    description = _(u'Allocate available dates on the resource')

    ignoreContext = True

    @button.buttonAndHandler(_(u'Allocate'))
    def allocate(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start = data['start']
        end = data['end']
        raster = data['raster']

        scheduler = self.context.scheduler
        scheduler.allocate(((start, end),), raster=raster)

        self.request.response.redirect(self.context.absolute_url())