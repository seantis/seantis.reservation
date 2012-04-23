import logging
logger = logging.getLogger('seantis.reservation')

from five import grok

from email.MIMEText import MIMEText
from email.Header import Header
from email.Utils import parseaddr, formataddr

from zope.app.component.hooks import getSite 
from plone.dexterity.content import Item
from plone.directives import form, dexterity
from plone.app.layout.viewlets.interfaces import IBelowContentBody
from plone.memoize import view
from Products.CMFCore.utils import getToolByName
from z3c.form import button

from seantis.reservation.form import ReservationDataView
from seantis.reservation.reserve import ReservationUrls
from seantis.reservation.interfaces import IReservationMadeEvent
from seantis.reservation.interfaces import IReservationApprovedEvent
from seantis.reservation.interfaces import IReservationDeniedEvent
from seantis.reservation.interfaces import OverviewletManager
from seantis.reservation.interfaces import IEmailTemplate
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
            send_reservation_mail(event.reservation, 'reservation_pending', event.language, to_managers=True)

@grok.subscribe(IReservationApprovedEvent)
def on_reservation_approved(event):
    if not settings.get('send_email_to_reservees', False):
        return
    if not event.reservation.autoapprovable:
        send_reservation_mail(event.reservation, 'reservation_approved', event.language)

@grok.subscribe(IReservationDeniedEvent)
def on_reservation_denied(event):
    if not settings.get('send_email_to_reservees', False):
        return
    if not event.reservation.autoapprovable:
        send_reservation_mail(event.reservation, 'reservation_denied', event.language)

class EmailTemplate(Item):
    def get_title(self):
        return _(u'Email Template') + u' ' + utils.native_language_name(self.language)

    def set_title(self, title):
        pass

    title = property(get_title, set_title)

def get_managers_by_context(context):
    managers = context.users_with_local_role('Reservation-Manager')
    
    if managers:
        return managers

    if not hasattr(context, 'portal_type'):
        return []

    if context.portal_type == 'Plone Site':
        return []

    return get_managers_by_context(context.aq_inner.aq_parent)

def get_manager_emails_by_context(context):
    managers = get_managers_by_context(context)

    if not managers:
        return []

    acl = utils.getToolByName(context, 'acl_users')
    groups = acl.source_groups.getGroupIds()

    # remove the groups and replace them with users
    users = []
    for man in managers:
        if man in groups:
            users.extend(acl.source_groups.getGroupById(man).getMemberIds())
        else:
            users.append(man)

    users = set(users)

    # go through the users and get their emails
    emails = []
    for user in users:
        emails.append(acl.getUserById(user).getProperty('email'))

    return emails

def get_email_content(context, email_type, language):
    user_templates = utils.portal_type_by_context(
        context, portal_type='seantis.reservation.emailtemplate'
    )

    for t in user_templates:
        if t.language != language:
            continue

        subject = getattr(t, email_type + '_subject')
        body = getattr(t, email_type + '_content')

        return subject, body

    return templates[email_type].get(language)
    
def send_reservation_mail(reservation, email_type, language, to_managers=False):

    context = getSite()
    resource = utils.get_resource_by_uuid(context, reservation.resource)

    # the resource doesn't currently exist in testing so we quietly
    # exit. This should be changed => #TODO
    if not resource:
        logging.warn('Cannot send email as the resource does not exist')
        return

    sender = utils.get_site_email_sender()

    if not sender:
        logging.warn('Cannot send email as no sender is configured')
        return

    resource = resource.getObject()

    if to_managers:
        recipients = get_manager_emails_by_context(resource)
        if not recipients:
            logger.warn("Couldn't find a manager to send an email to")
            return
    else:
        recipients = [reservation.email]

    subject, body = get_email_content(resource, email_type, language)

    for recipient in recipients:
        mail = ReservationMail(resource, reservation,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body
        )

        send_mail(resource, mail)

def send_mail(context, mail):
    try:
        context.MailHost.send(mail.as_string(), immediate=False)
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

        # title of the resource
        if is_needed('resource'):
            p['resource'] = utils.get_resource_title(resource)

        # reservation email
        if is_needed('reservation_mail'):
            p['reservation_mail'] = reservation.email

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

# The following is quite similar to the timeframe.py stuff
# surely this can be merged somewhat => #TODO

def validate_template(context, request, data):
    if context.portal_type == 'seantis.reservation.emailtemplate':
        folder = context.aq_inner.aq_parent
    else:
        folder = context
    
    templates = utils.portal_type_in_context(
        folder, portal_type='seantis.reservation.emailtemplate'
    )

    duplicate = False

    for template in templates:
        if template.id == context.id:
            continue

        if template.getObject().title == context.title:
            duplicate = True
            break

    if duplicate:
        msg = utils.translate(context, request, 
            _(u"There's already an Email template in the same folder for the same language")
        )
        utils.form_error(msg)

class TemplateAddForm(dexterity.AddForm):

    permission = 'cmf.AddPortalContent'

    grok.context(IEmailTemplate)
    grok.require(permission)

    grok.name('seantis.reservation.emailtemplate')

    @button.buttonAndHandler(_('Save'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        validate_template(self.context, self.request, data)
        dexterity.AddForm.handleAdd(self, action)

class TemplateEditForm(dexterity.EditForm):

    permission = 'cmf.ModifyPortalContent'

    grok.context(IEmailTemplate)
    grok.require(permission)

    @button.buttonAndHandler(_(u'Save'), name='save')
    def handleApply(self, action):
        data, errors = self.extractData()
        validate_template(self.context, self.request, data)
        dexterity.EditForm.handleApply(self, action)

class TemplatesViewlet(grok.Viewlet):

    permission = 'cmf.ModifyPortalContent'

    grok.context(form.Schema)
    grok.require(permission)

    grok.name('seantis.reservation.mailviewlet')
    grok.viewletmanager(OverviewletManager)

    grok.order(4)

    _template = grok.PageTemplateFile('templates/email_templates.pt')

    @view.memoize
    def templates(self):
        templates = [t.getObject() for t in utils.portal_type_in_context(
            self.context, portal_type='seantis.reservation.emailtemplate'
        )]
        return sorted(templates, key=lambda t: t.title)

    def links(self, template=None):

        # global links
        if not template:
            baseurl = self.context.absolute_url()
            return [(_(u'Add email template'),
                baseurl + '/++add++seantis.reservation.emailtemplate')]

        # template specific links
        links = []
        
        baseurl = template.absolute_url()
        links.append((_(u'Edit'), baseurl + '/edit'))
        links.append((_(u'Delete'), baseurl + '/delete_confirmation'))
        
        return links

    def render(self, **kwargs):
        if self.context == None:
            return u''
        
        return self._template.render(self)