from five import grok
from seantis.reservation.interfaces import ISeantisReservationSpecific


class BaseView(grok.View):

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)


class BaseViewlet(grok.Viewlet):

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)
