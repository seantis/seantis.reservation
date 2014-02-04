import tablib

from zope import i18n
from zope.i18nmessageid import Message

from sqlalchemy.sql.expression import extract

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import utils
from seantis.reservation.form import ReservationDataView
from seantis.reservation.models import Reservation


class Translator(object):

    def __init__(self, language):
        self.language = language

    def translate(self, obj):
        if isinstance(obj, Message):
            return self.translate_text(obj)

        if isinstance(obj, list):
            return self.translate_list(obj)

        raise NotImplementedError

    def translate_text(self, text):
        assert isinstance(text, Message)
        return i18n.translate(text, target_language=self.language)

    def translate_list(self, _list):
        # translate the values in the record
        for i, item in enumerate(_list):
            if isinstance(item, Message):
                _list[i] = self.translate_text(item)

        return _list


def basic_headers():
    return [
        _(u'Parent'),
        _(u'Resource'),
        _(u'Token'),
        _(u'Email'),
        _(u'Start'),
        _(u'End'),
        _(u'Whole Day'),
        _(u'Status'),
        _(u'Quota'),
        _(u'Created'),
        _(u'Modified')
    ]


def dataset(
    resources, language, year, month, transform_record=None, compact=False
):
    """ Takes a list of resources and returns a tablib dataset filled with
    all reservations of these resources. The json data of the reservations
    is filled using a single column for each type (form + field).

    transform_record is called before each record is added to the dataset. It
    allows for changes to the dataset, which is hard otherwise because the
    records are stored as tuples in the dataset and not meant to be changed.

    If compact is True, whole day group reservations spanning multiple days
    are merged into one using utils.unite_dates.

    """

    translator = Translator(language)
    reservations = fetch_records(resources, year, month)

    # create the headers
    headers = translator.translate(basic_headers())
    dataheaders = additional_headers(reservations)
    headers.extend(dataheaders)

    # use dataview for display info helper view (yep, could be nicer)
    dataview = ReservationDataView()

    # for each reservation get a record per timeslot (which is a single slot
    # for reservations targeting an allocation and n slots for a reservation
    # targeting a group)
    records = []
    for r in reservations:

        token = utils.string_uuid(r.token)
        resource = resources[utils.string_uuid(r.resource)]

        if compact:
            timespans = utils.unite_dates(r.timespans())
        else:
            timespans = r.timespans()

        for start, end in timespans:
            record = [
                get_parent_title(resource),
                resource.title,
                token,
                r.email,
                start,
                end,
                utils.whole_day(start, end),
                _(r.status.capitalize()),
                r.quota,
                r.created,
                r.modified and r.modified or None,
            ]
            record.extend(
                additional_columns(
                    r, dataheaders, dataview.display_reservation_data
                )
            )

            if callable(transform_record):
                transform_record(record)

            translator.translate(record)
            records.append(record)

    # put the results in a tablib dataset
    return generate_dataset(headers, records)


def fetch_records(resources, year, month):
    """ Returns the records used for the dataset. """
    if not resources.keys():
        return []

    query = Session.query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))

    if year != 'all':
        query = query.filter(extract('year', Reservation.start) == int(year))

    if month != 'all':
        query = query.filter(extract('month', Reservation.start) == int(month))

    query = query.order_by(
        Reservation.resource,
        Reservation.status,
        Reservation.start,
        Reservation.email,
        Reservation.token,
    )

    return query.all()


def fieldkey(form, field):
    """ Returns the fieldkey for any given json data field + form. """
    return '%s.%s' % (form["desc"], field["desc"])


def additional_headers(reservations):
    """ Go through all reservations and build a list of all possible headers.

    """

    formdata = [r.data.values() for r in reservations if r.data]

    headers = []
    for forms in formdata:
        for form in forms:
            for field in sorted(form["values"], key=lambda f: f["sortkey"]):

                # A set could be used here, but then a separate step for
                # sorting would be needed
                key = fieldkey(form, field)
                if not key in headers:
                    headers.append(key)

    return headers


def additional_columns(reservation, headers, display_info=lambda x: x):
    """ Given a reservation and the list of additional headers return a list
    of columns filled with either None or the value of the json data.

    The resulting list will always be of the same length as the given headers
    list.

    """
    forms = reservation.data and reservation.data.values() or []

    columns = [None] * len(headers)
    for form in forms:
        for field in form["values"]:
            key = fieldkey(form, field)
            idx = headers.index(key)

            columns[idx] = field["value"]

    return columns


def generate_dataset(headers, records):
    ds = tablib.Dataset()
    ds.headers = headers

    for r in records:
        ds.append(r)

    return ds


def get_parent_title(resource):
    # a parent will almost always be present, but it isn't a requirement
    try:
        return resource.aq_inner.aq_parent.title
    except AttributeError:
        return None
