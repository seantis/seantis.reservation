from datetime import datetime
from datetime import timedelta

from five import grok
from zope import schema
from zope.interface import Interface
from plone.directives import form
from z3c.form import field
from z3c.form import button

from seantis.reservation import _
from seantis.reservation import resource
from seantis.reservation.raster import rasterize_start

class IReserveForm(Interface):

    start = schema.Datetime(
        title=_(u'From')
        )

    end = schema.Datetime(
        title=_(u'To')
        )

class ReserveForm(form.Form):
    grok.context(resource.IResource)
    grok.name('reserve')
    grok.require('cmf.ManagePortal')

    fields = field.Fields(IReserveForm)

    label = _(u'Resource reservation')
    description = _(u'Reserve available dates on the resource')

    ignoreContext = True

    def update(self, **kwargs):
        try:
            start = self.request.get('start')
            if start:
                start = datetime.fromtimestamp(float(start))
            else:
                start = rasterize_start(datetime.now(), 60)

            end = self.request.get('end')
            if end:
                end = datetime.fromtimestamp(float(end))
            else:
                start += timedelta(minutes=60)

            self.fields['start'].field.default = start
            self.fields['end'].field.default = end
        
        except TypeError:
            pass

        finally:
            super(ReserveForm, self).update(**kwargs)

    @button.buttonAndHandler(_(u'Reserve'))
    def reserve(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        start = data['start']
        end = data['end']

        scheduler = self.context.scheduler
        scheduler.reserve(((start, end),))

        self.request.response.redirect(self.context.absolute_url())