import codecs

from five import grok
from zope.interface import Interface

from seantis.reservation import form
from seantis.reservation import exports

sources = {
    'reservations': exports.reservations.dataset
}

extensions = ['xls','csv', 'json']

class ExportView(grok.View, form.ResourceParameterView):
    """Exports the reservations from a list of resources. """

    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)

    grok.context(Interface)
    grok.baseclass()

    @property
    def content_type(self):
        raise NotImplementedError

    @property
    def file_extension(self):
        raise NotImplementedError

    @property
    def language(self):
        return self.request.get('lang', 'en')

    @property
    def source(self):
        source = sources.get(self.request.get('source'))
        
        if not source:
            raise NotImplementedError

        return lambda: source(self.context, self.request, self.resources, self.language)

    def render(self, **kwargs):
        filename = '%s.%s' % (self.context.title, self.file_extension)
        filename = codecs.utf_8_encode('filename="%s"' % filename)[0]
        
        dataset = self.source()
        output = getattr(dataset, self.file_extension)

        RESPONSE = self.request.RESPONSE
        RESPONSE.setHeader("Content-disposition", filename)
        RESPONSE.setHeader("Content-Type", "%s;charset=utf-8" % self.content_type)
        RESPONSE.setHeader("Content-Length", len(output))

        return output

class XlsExportView(ExportView):
    grok.name('resource_export.xls')
    content_type = 'application/xls'
    file_extension = 'xls'

class JsonExportView(ExportView):
    grok.name('resource_export.json')
    content_type = 'application/json'
    file_extension = 'json'

class CsvExportView(ExportView):
    grok.name('resource_export.csv')
    content_type = 'application/csv'
    file_extension = 'csv'