import tablib

from zope import i18n
from zope.i18nmessageid import Message

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import utils
from seantis.reservation.form import ReservationDataView
from seantis.reservation.models import Reservation


def translator(language):
    """ Returns a function which will return the translation for a given text
    in the once defined language.

    """
    def curried(text):
        assert isinstance(text, Message)
        return i18n.translate(text, target_language=language)

    return curried


def dataset(resources, language):
    """ Takes a list of resources and returns a tablib dataset filled with
    all reservations of these resources. The json data of the reservations
    is filled using a single column for each type (form + field).

    """

    text = translator(language)
    reservations = fetch_records(resources)

    # create the headers
    headers = [
        text(_(u'Parent')),
        text(_(u'Resource')),
        text(_(u'Token')),
        text(_(u'Email')),
        text(_(u'Start')),
        text(_(u'End')),
        text(_(u'Status')),
        text(_(u'Quota')),
    ]
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

        # a parent will almost always be present, but it isn't a requirement
        if hasattr(resource, 'parent'):
            parent_title = resource.parent().title
        else:
            parent_title = None

        for start, end in r.timespans():
            record = [
                parent_title,
                resource.title,
                token,
                r.email,
                start.strftime('%Y-%m-%d %H:%M'),
                end.strftime('%Y-%m-%d %H:%M'),
                _(r.status.capitalize()),
                r.quota
            ]
            record.extend(
                additional_columns(r, dataheaders, dataview.display_info)
            )

            # translate the values in the record
            for i, col in enumerate(record):
                if isinstance(col, Message):
                    record[i] = text(col)

            records.append(record)

    # put the results in a tablib dataset
    ds = tablib.Dataset()
    ds.headers = headers
    for r in records:
        ds.append(r)

    return ds


def fetch_records(resources):
    """ Returns the records used for the dataset. """
    query = Session.query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))
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
    formdata = [r.data.values() for r in reservations]

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
    forms = reservation.data.values()

    columns = [None] * len(headers)
    for form in forms:
        for field in form["values"]:
            key = fieldkey(form, field)
            idx = headers.index(key)

            columns[idx] = display_info(field["value"])

    return columns
