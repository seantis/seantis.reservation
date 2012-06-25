import tablib
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

    headers = (
        text(_(u'Parent')),
        text(_(u'Resource')),
        text(_(u'Token')),
        text(_(u'Email')),
        text(_(u'Start')),
        text(_(u'End')),
        text(_(u'Status')),
    )

    reservations = fetch_records(resources)

    records = []
    for r in reservations:
        token = utils.string_uuid(r.token)
        resource = resources[utils.string_uuid(r.resource)]
        parent = resource.parent()
        for start, end in r.timespans():
            records.append((
                resource.title,
                parent.title,
                token,
                r.email,
                start.strftime('%Y-%m-%d %H:%M'),
                end.strftime('%Y-%m-%d %H:%M'),
                r.status
            ))

    ds = tablib.Dataset()
    ds.headers = headers
    for r in records:
        ds.append(r)

    return ds

def fetch_records(resources):
    query = Session.query(Reservation)
    query = query.filter(Reservation.resource.in_(resources.keys()))

    return query.all()