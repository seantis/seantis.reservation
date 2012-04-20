from email.MIMEText import MIMEText
from email.Header import Header
from email.Utils import parseaddr, formataddr

from five import grok
from zope.app.component.hooks import getSite 
from plone.dexterity.content import Item

from seantis.reservation.form import ReservationDataView
from seantis.reservation.reserve import ReservationUrls
from seantis.reservation.interfaces import IReservationMadeEvent
from seantis.reservation.interfaces import IReservationApprovedEvent
from seantis.reservation.interfaces import IReservationDeniedEvent
from seantis.reservation.mail_templates import templates
from seantis.reservation import utils
from seantis.reservation import settings
from seantis.reservation import _

@grok.subscribe(IReservationMadeEvent)
def on_reservation_made(event):
    if event.reservation.autoapprovable:
        if settings.get('send_email_to_reservees', True):
            send_reservation_mail(event.reservation, 'reservation_autoapproved', event.language)
    else:
        if settings.get('send_email_to_reservees', True):
            send_reservation_mail(event.reservation, 'reservation_received', event.language)

        if settings.get('send_email_to_managers', True):
            send_reservation_mail(event.reservation, 'reservation_pending', event.language)

@grok.subscribe(IReservationApprovedEvent)
def on_reservation_approved(event):
    if not settings.get('send_email_to_reservees', False):
        return
    if not event.reservation.autoapprovable:
        send_reservation_mail(event.reservation, 'reservation_approved', event.language)

@grok.subscribe(IReservationDeniedEvent)
def on_reservation_denied(event):
    if not settings.get('send_email_to_reservees', False):
        if not event.reservation.autoapprovable:
            send_reservation_mail(event.reservation, 'reservation_denied', event.language)

class EmailTemplate(Item):
    def get_title(self):
        return _(u'Email Template') + u' ' + utils.native_language_name(self.language)

    def set_title(self, title):
        pass

    title = property(get_title, set_title)

def send_reservation_mail(reservation, email_type, language):

    context = getSite()
    resource = utils.get_resource_by_uuid(context, reservation.resource)

    # the resource doesn't currently exist in testing so we quietly
    # exit. This should be changed => #TODO
    if not resource:
        return

    subject, body = templates[email_type].get(language)

    mail = ReservationMail(resource, reservation,
        sender='noreply@example.com',
        recipient=reservation.email,
        subject=subject,
        body=body
    )

    send_mail(resource, mail)

def send_mail(context, mail):
    try:
        context.MailHost.send(mail.as_string(), immediate=True)
    except Exception, e:
        print e
        pass # TODO add logging

class ReservationMail(ReservationDataView, ReservationUrls):

    sender=u''
    recipient=u''
    subject=u''
    body=u''

    def __init__(self, resource, reservation, **kwargs):
        for k,v in kwargs.items():
            if hasattr(self, k): setattr(self, k, v)

        # get information for the body/subject string

        p = dict()
        is_needed = lambda key: key in self.subject or key in self.body

        resource = resource.getObject()

        # title of the resource
        if is_needed('resource'):
            p['resource'] = utils.get_resource_title(resource)

        # reservation email
        if is_needed('reservation_mail'):
            p['reservation_mail'] = self.recipient

        # a list of dates
        if is_needed('dates'):
            lines = []
            dates = sorted(reservation.timespans(), key=lambda i: i[0])
            for start, end in dates:
                line = start.strftime('%d.%m.%Y %H:%M')
                line += ' - '
                line += end.strftime('%H:%M')

                lines.append(line)

            p['dates'] = '\n'.join(lines)

        # tabbed reservation data
        if is_needed('data'):
            data = reservation.data
            lines = []
            for key in self.sorted_info_keys(data):
                interface = data[key]

                lines.append(interface['desc'])
                for value in self.sorted_values(interface['values']):
                    lines.append('\t' + value['desc'] + ': '+ self.display_info(value['value']))


            p['data'] = '\n'.join(lines)

        # approval link
        if is_needed('approval_link'):
            p['approval_link'] = self.approve_all_url(reservation.token, resource)

        # denial links
        if is_needed('denial_link'):
            p['denial_link'] = self.deny_all_url(reservation.token, resource)

        self.parameters = p

    def as_string(self):
        subject = self.subject % self.parameters
        body = self.body % self.parameters
        mail = create_email(self.sender, self.recipient, subject, body)
        return mail.as_string()

def create_email(sender, recipient, subject, body):
    """Create an email message.

    All arguments should be Unicode strings (plain ASCII works as well).

    Only the real name part of sender and recipient addresses may contain
    non-ASCII characters.

    The charset of the email will be the UTF-8.
    """

    header_charset = 'UTF-8'
    body_charset = 'UTF-8'

    body.encode(body_charset)

    # Split real name (which is optional) and email address parts
    sender_name, sender_addr = parseaddr(sender)
    recipient_name, recipient_addr = parseaddr(recipient)

    # We must always pass Unicode strings to Header, otherwise it will
    # use RFC 2047 encoding even on plain ASCII strings.
    sender_name = str(Header(unicode(sender_name), header_charset))
    recipient_name = str(Header(unicode(recipient_name), header_charset))

    # Make sure email addresses do not contain non-ASCII characters
    sender_addr = sender_addr.encode('ascii')
    recipient_addr = recipient_addr.encode('ascii')

    # Create the message ('plain' stands for Content-Type: text/plain)
    msg = MIMEText(body.encode(body_charset), 'plain', body_charset)
    msg['From'] = formataddr((sender_name, sender_addr))
    msg['To'] = formataddr((recipient_name, recipient_addr))
    msg['Subject'] = Header(unicode(subject), header_charset)

    return msg