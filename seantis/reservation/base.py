from five import grok

from plone.app.layout.globals.layout import LayoutPolicy
from plone.directives.form import Form

from seantis.plonetools import tools
from seantis.reservation.interfaces import ISeantisReservationSpecific


class BaseView(grok.View):

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)

    def translate(self, text):
        return tools.translator(self.request, 'seantis.reservation')(text)


class BaseViewlet(grok.Viewlet):

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)


class BaseForm(Form):

    grok.baseclass()
    grok.layer(ISeantisReservationSpecific)


class ReservationLayoutPolicy(LayoutPolicy):

    def bodyClass(self, template, view):
        """Returns the CSS class to be used on the body tag.
        """

        body_class = LayoutPolicy.bodyClass(self, template, view)

        additional_classes = [
            'seantis-reservation-view'
        ]

        if hasattr(view, 'body_classes'):
            view_body_classes = view.body_classes

            if view_body_classes:
                additional_classes.extend(view.body_classes)

        return '{} {}'.format(body_class, ' '.join(additional_classes))
