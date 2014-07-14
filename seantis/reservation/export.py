import codecs
import isodate

from copy import copy
from collections import namedtuple
from datetime import datetime, date, time

from five import grok
from zope import schema
from zope.interface import Interface
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from z3c.form import field
from z3c.form import button

from plone import api
from plone.app.textfield.value import RichTextValue

from seantis.plonetools import tools

from seantis.reservation import _
from seantis.reservation import form
from seantis.reservation import utils
from seantis.reservation import exports
from seantis.reservation.form import extract_action_data
from seantis.reservation.base import BaseView, BaseForm

Source = namedtuple('Source', ['id', 'title', 'description', 'method'])

sources = [
    Source(
        'reservations', _(u'Reservations (Normal)'),
        _(
            u'The default reservations export with every date in the resource '
            u'having a separate record.'
        ),
        lambda resources, language, year, month, transform_record:
        exports.reservations.dataset(
            resources, language, year, month, transform_record, compact=False
        )
    ),

    Source(
        'united-reservations', _(u'Reservations (Compact)'),
        _(
            u'Like the normal reservations export, but with '
            u'group-reservations spanning multiple days merged into single '
            u'records.'
        ),
        lambda resources, language, year, month, transform_record:
        exports.reservations.dataset(
            resources, language, year, month, transform_record, compact=True
        )
    )
]


extensions = {
    'xls': _(u'Excel Format (XLS)'),
    'xlsx': _(u'Excel Format (XLSX)'),
    'csv': _(u'CSV Format'),
    'json': _(u'JSON Format'),
}


def get_sources_description(request):
    translate = tools.translator(request, 'seantis.reservation')

    items = [
        u'<dt>{}</dt><dd>{}</dd>'.format(
            *map(translate, (s.title, s.description))
        ) for s in sources
    ]

    return u'<dl>{}</dl>'.format(''.join(items))


@grok.provider(IContextSourceBinder)
def year_choices(context):
    years = [
        SimpleTerm(value=u'all', title=_(u'All'))
    ]

    minyear = datetime.now().year - 5
    maxyear = datetime.now().year + 1

    for year in range(minyear, maxyear + 1):
        years.append(
            SimpleTerm(value=unicode(year), title=unicode(year))
        )

    return SimpleVocabulary(years)


month_choices = SimpleVocabulary(
    [
        SimpleTerm(value=u'all', title=_(u'All')),
        SimpleTerm(value=u'1', title=_(u'January')),
        SimpleTerm(value=u'2', title=_(u'February')),
        SimpleTerm(value=u'3', title=_(u'March')),
        SimpleTerm(value=u'4', title=_(u'April')),
        SimpleTerm(value=u'5', title=_(u'May')),
        SimpleTerm(value=u'6', title=_(u'June')),
        SimpleTerm(value=u'7', title=_(u'July')),
        SimpleTerm(value=u'8', title=_(u'August')),
        SimpleTerm(value=u'9', title=_(u'September')),
        SimpleTerm(value=u'10', title=_(u'October')),
        SimpleTerm(value=u'11', title=_(u'November')),
        SimpleTerm(value=u'12', title=_(u'December')),
    ]
)

export_choices = SimpleVocabulary(
    [SimpleTerm(value=source.id, title=source.title) for source in sources]
)

format_choices = SimpleVocabulary(
    [
        SimpleTerm(value=ext, title=name)
        for ext, name in sorted(extensions.items(), key=lambda i: i[1])
    ]
)


class IExportSelection(Interface):
    """ Configuration for all exports. """

    export = schema.Choice(
        title=_(u'Export'),
        source=export_choices,
        required=True,
        default=sources[0].id,
    )

    format = schema.Choice(
        title=_(u'Format'),
        source=format_choices,
        required=True,
        default=extensions.keys()[0]
    )

    year = schema.Choice(
        title=_(u"Year"),
        source=year_choices,
        required=True,
        default=u'all'
    )

    month = schema.Choice(
        title=_(u"Month"),
        source=month_choices,
        required=True,
        default=u'all'
    )


class ExportSelection(BaseForm, form.ResourceParameterView):
    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)
    grok.context(Interface)
    grok.name('reservation-exports')

    label = _(u'Reservation Export')

    fields = field.Fields(IExportSelection)
    ignoreContext = True

    enable_unload_protection = False

    @property
    def action(self):
        return u'{base}/reservation-exports?uuid={uuids}'.format(
            base=self.context.absolute_url(),
            uuids='&uuid='.join(self.uuids)
        )

    def build_export_url(self, data):
        if not self.uuids:
            utils.form_error(_(u"Missing 'uuid' parameter"))

        url_template = (
            u'{base}/reservation-export.{format}?source={export}&uuid={uuids}'
            u'&year={year}&month={month}'
        )

        data['base'] = self.context.absolute_url()
        data['uuids'] = '&uuid='.join(self.uuids)

        return url_template.format(**data)

    def updateActions(self):
        super(ExportSelection, self).updateActions()
        self.actions['export'].addClass('allowMultiSubmit')
        self.actions['export'].addClass('context')

    def update(self):
        self.fields['export'].field = copy(self.fields['export'].field)
        self.fields['export'].field.description = get_sources_description(
            self.request
        )
        super(ExportSelection, self).update()

    @button.buttonAndHandler(_(u'Export'))
    @extract_action_data
    def export(self, data):
        self.request.response.redirect(self.build_export_url(data))

    @button.buttonAndHandler(_(u'Cancel'))
    @extract_action_data
    def cancel(self, data):
        self.request.response.redirect(self.context.absolute_url())


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


class ExportView(BaseView, form.ResourceParameterView):
    """Exports the reservations from a list of resources. """

    permission = 'seantis.reservation.ViewReservations'
    grok.require(permission)

    grok.context(Interface)
    grok.baseclass()

    def get_source_by_id(self, source_id):
        source = next((s for s in sources if s.id == source_id), None)

        if not source:
            raise NotImplementedError

        return source

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
    def year(self):
        return self.request.get('year', 'any')

    @property
    def month(self):
        return self.request.get('month', 'any')

    @property
    def source(self):
        source = self.get_source_by_id(self.request.get('source'))
        transform_record = lambda r: prepare_record(r, self.file_extension)

        return lambda: source.method(
            self.resources,
            self.language,
            self.year,
            self.month,
            transform_record
        )

    @property
    def filename(self):
        parts = []

        parts.append(self.context.title)

        source = self.get_source_by_id(self.request.get('source'))
        translate = tools.translator(self.request, 'seantis.reservation')
        parts.append(translate(source.title))

        if self.year not in ('any', 'all'):
            parts.append(self.year)

        if self.month not in ('any', 'all'):
            if len(self.month) == 1:
                parts.append('0{}'.format(self.month))
            else:
                parts.append(self.month)

        parts.append(self.file_extension)

        return '.'.join(parts)

    def render(self, **kwargs):
        output = getattr(self.source(), self.file_extension)

        RESPONSE = self.request.RESPONSE
        RESPONSE.setHeader(
            "Content-disposition",
            codecs.utf_8_encode('filename="{}"'.format(self.filename))[0]
        )
        RESPONSE.setHeader(
            "Content-Type", "{};charset=utf-8".format(self.content_type)
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
