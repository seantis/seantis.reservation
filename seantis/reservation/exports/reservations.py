import tablib
import json

from zope import i18n

from seantis.reservation import _
from seantis.reservation import Session
from seantis.reservation import utils
from seantis.reservation.models import Reservation


def translator(language):
    def curried(text):
        return i18n.translate(text, target_language=language)

    return curried

def dataset(context, request, resources, language):
    text = translator(language)
    reservations = fetch_records(resources)

    headers = [
        text(_(u'Parent')),
        text(_(u'Resource')),
        text(_(u'Token')),
        text(_(u'Email')),
        text(_(u'Start')),
        text(_(u'End')),
        text(_(u'Status')),
    ]
    baseheaders = len(headers)
    headers.extend(additional_headers(reservations))

    records = []
    for r in reservations:
        token = utils.string_uuid(r.token)
        resource = resources[utils.string_uuid(r.resource)]
        parent = resource.parent()
        for start, end in r.timespans():
            record = [
                resource.title,
                parent.title,
                token,
                r.email,
                start.strftime('%Y-%m-%d %H:%M'),
                end.strftime('%Y-%m-%d %H:%M'),
                text(_(r.status.capitalize()))
            ]
            record.extend(additional_columns(r, headers[baseheaders:]))

            records.append(record)

    ds = tablib.Dataset()
    ds.headers = headers
    for r in records:
        ds.append(r)

    return ds

def fetch_records(resources):
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
    return '%s.%s' % (form["desc"], field["desc"])

def additional_headers(reservations):
    formdata = [r.data.values() for r in reservations]

    headers = []
    for forms in formdata:
        for form in forms:
            for field in sorted(form["values"], key=lambda f: f["sortkey"]):
                key = fieldkey(form, field)
                if not key in headers:
                    headers.append(key)

    return headers

def additional_columns(reservation, headers):
    forms = reservation.data.values()

    columns = [None] * len(headers)
    for form in forms:
        for field in form["values"]:
            key = fieldkey(form, field)
            idx = headers.index(key)

            columns[idx] = field["value"]

    return columns
