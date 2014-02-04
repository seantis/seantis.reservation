from five import grok
from zope.interface import Interface

from seantis.reservation.reserve import ReservationUrls
from seantis.reservation.form import ReservationDataView
from seantis.reservation import utils
from seantis.reservation.base import BaseView


class View(BaseView, ReservationUrls, ReservationDataView):
    """A numer of macros for use with seantis.dir.base"""

    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('seantis-reservation-macros')

    template = grok.PageTemplateFile('templates/macros.pt')

    def __getitem__(self, key):
        return self.template._template.macros[key]

    @property
    def utils(self):
        return utils
