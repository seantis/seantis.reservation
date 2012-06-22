import xlwt
import codecs

from StringIO import StringIO

from five import grok
from zope.interface import Interface

from seantis.reservation import form

class XlsExportView(grok.View, form.ResourceParameterView):
    """Exports the reservations from a list of resources. """

    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)

    grok.context(Interface)
    grok.name('excel_export') # note that this text is copied in utils.py

    def render(self, **kwargs):

        xlsfile = StringIO()
        filename = '%s.xls' % self.context.title
        filename = codecs.utf_8_encode('filename="%s"' % filename)[0]
        
        try:    
            output = xlsfile.getvalue()
        finally:
            xlsfile.close()

        RESPONSE = self.request.RESPONSE
        RESPONSE.setHeader("Content-disposition", filename)
        RESPONSE.setHeader("Content-Type", "application/xls")
        RESPONSE.setHeader("Content-Length", len(output))

        return output