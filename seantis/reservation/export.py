import codecs
from collections import namedtuple

from five import grok
from zope.interface import Interface

from seantis.reservation import _
from seantis.reservation import form
from seantis.reservation import utils
from seantis.reservation import exports

Source = namedtuple('Source', ['id', 'title', 'description', 'method'])

sources = [
    Source('reservations', _(u'Reservations (Normal)'), 
        _(
            u'The default reservations export with every date in the resource '
            u'having a separate record.'
        ), 
        lambda resources, language: exports.reservations.dataset(
            resources, language, compact=False
        )
    ),

    Source('united-reservations', _(u'Reservations (Compact)'), 
        _(
            u'Like the normal reservations export, but with '
            u'group-reservations spanning multiple days merged into single '
            u'records.'
        ), 
        lambda resources, language: exports.reservations.dataset(
            resources, language, compact=True
        )
    )
]


extensions = {
    'xls': _(u'Excel Format'),
    'csv': _(u'CSV Format'),
    'json': _(u'JSON Format')
}


def get_exports(context, request, uuids):
    Export = namedtuple(
        'Export', ('urls', 'title', 'description')
    )

    Url = namedtuple(
        'Url', ('href', 'title')
    )

    translate = utils.translator(context, request)

    query = '&uuid='.join(uuids)
    urltemplate = ''.join(
        (
            context.absolute_url(), 
            '/reservation-export.{ext}?source={id}&uuid=', 
            query
        )
    )

    exports = []
    for source in sources:
        
        urls = []
        for extension, title in extensions.items():
            urls.append(
                Url(
                    urltemplate.format(ext=extension, id=source.id),
                    translate(title)
                )
            )
        exports.append(Export(
            urls,
            translate(source.title),
            translate(source.description),
        ))

    return exports


class ExportListView(grok.View, form.ResourceParameterView):
    """Shows the available exports for the resource. """

    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)
    grok.context(Interface)
    grok.name('reservation-exports')
    
    template = grok.PageTemplateFile('templates/reservation_exports.pt')

    title = _(u'Export Reservations')

    def exports(self):
        return get_exports(self.context, self.request, self.uuids)
        


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
        source_id = self.request.get('source')
        source = next((s for s in sources if s.id == source_id), None)

        if not source:
            raise NotImplementedError

        return lambda: source.method(self.resources, self.language)

    def render(self, **kwargs):
        filename = '%s.%s' % (self.context.title, self.file_extension)
        filename = codecs.utf_8_encode('filename="%s"' % filename)[0]

        dataset = self.source()
        output = getattr(dataset, self.file_extension)

        RESPONSE = self.request.RESPONSE
        RESPONSE.setHeader("Content-disposition", filename)
        RESPONSE.setHeader(
            "Content-Type", "%s;charset=utf-8" % self.content_type
        )
        RESPONSE.setHeader("Content-Length", len(output))

        return output


class XlsExportView(ExportView):
    grok.name('reservation-export.xls')
    content_type = 'application/xls'
    file_extension = 'xls'


class JsonExportView(ExportView):
    grok.name('reservation-export.json')
    content_type = 'application/json'
    file_extension = 'json'


class CsvExportView(ExportView):
    grok.name('reservation-export.csv')
    content_type = 'application/csv'
    file_extension = 'csv'
