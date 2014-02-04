import codecs
import isodate

from collections import namedtuple
from datetime import datetime, date, time

from five import grok
from zope.interface import Interface

from plone import api
from plone.app.textfield.value import RichTextValue

from seantis.reservation import _
from seantis.reservation import form
from seantis.reservation import utils
from seantis.reservation import exports
from seantis.reservation.base import BaseView

Source = namedtuple('Source', ['id', 'title', 'description', 'method'])

sources = [
    Source(
        'reservations', _(u'Reservations (Normal)'),
        (
            u'The default reservations export with every date in the resource '
            u'having a separate record.'
        ),
        lambda resources, language, transform_record:
        exports.reservations.dataset(
            resources, language, transform_record, compact=False
        )
    ),

    Source(
        'united-reservations', _(u'Reservations (Compact)'),
        (
            u'Like the normal reservations export, but with '
            u'group-reservations spanning multiple days merged into single '
            u'records.'
        ),
        lambda resources, language, transform_record:
        exports.reservations.dataset(
            resources, language, transform_record, compact=True
        )
    )
]


extensions = {
    'xls': _(u'Excel Format (XLS)'),
    'xlsx': _(u'Excel Format (XLSX)'),
    'csv': _(u'CSV Format'),
    'json': _(u'JSON Format'),
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
        for extension, title in sorted(extensions.items(), key=lambda i: i[1]):
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

    return sorted(exports, key=lambda src: src.title)


def convert_datelikes_to_isoformat(record):
    for ix, value in enumerate(record):
        if isinstance(value, datetime):
            record[ix] = isodate.datetime_isoformat(value)
        elif isinstance(value, date):
            record[ix] = isodate.date_isoformat(value)
        elif isinstance(value, time):
            record[ix] = isodate.date_isoformat(value)


def extract_text_from_richtext(record):
    transforms = api.portal.get_tool('portal_transforms')

    for ix, value in enumerate(record):
        if isinstance(value, RichTextValue):
            stream = transforms.convertTo(
                'text/plain', value.output, mimetype='text/html'
            )
            record[ix] = stream.getData().strip()


def convert_boolean_to_yes_no(record):
    for ix, value in enumerate(record):
        if isinstance(value, bool):
            record[ix] = _(u'Yes') if value is True else _(u'No')


def prepare_record(record, target_format):

    if target_format in ('xls', 'xlsx'):
        convert_boolean_to_yes_no(record)

    convert_datelikes_to_isoformat(record)
    extract_text_from_richtext(record)

    return record


class ExportListView(BaseView, form.ResourceParameterView):
    """Shows the available exports for the resource. """

    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)
    grok.context(Interface)
    grok.name('reservation-exports')

    template = grok.PageTemplateFile('templates/reservation_exports.pt')

    title = _(u'Export Reservations')

    def exports(self):
        return get_exports(self.context, self.request, self.uuids)


class ExportView(BaseView, form.ResourceParameterView):
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

        transform_record = lambda r: prepare_record(r, self.file_extension)

        return lambda: source.method(
            self.resources, self.language, transform_record
        )

    def render(self, **kwargs):
        filename = '%s.%s' % (self.context.title, self.file_extension)
        filename = codecs.utf_8_encode('filename="%s"' % filename)[0]

        output = getattr(self.source(), self.file_extension)

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


class XlsxExportView(ExportView):
    grok.name('reservation-export.xlsx')
    content_type = 'application/xlsx'
    file_extension = 'xlsx'


class JsonExportView(ExportView):
    grok.name('reservation-export.json')
    content_type = 'application/json'
    file_extension = 'json'


class CsvExportView(ExportView):
    grok.name('reservation-export.csv')
    content_type = 'application/csv'
    file_extension = 'csv'
