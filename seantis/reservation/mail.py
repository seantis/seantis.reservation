from itertools import groupby

import logging
log = logging.getLogger('seantis.reservation')

from five import grok

from email.MIMEText import MIMEText
from email.Header import Header
from email.Utils import parseaddr, formataddr

from plone.dexterity.content import Item
from plone.directives import dexterity
from plone.memoize import view
from Products.CMFCore.interfaces import IFolderish
from Products.CMFCore.utils import getToolByName
from z3c.form import button
from zope.schema import getFields

from seantis.reservation import _
from seantis.reservation import settings
from seantis.reservation import utils
from seantis.reservation.base import BaseViewlet
from seantis.reservation.form import ReservationDataView
from seantis.reservation.interfaces import (
    IEmailTemplate,
    IReservationTimeChangedEvent,
    IReservationsApprovedEvent,
    IReservationsConfirmedEvent,
    IReservationsDeniedEvent,
    IReservationsRevokedEvent,
    ISeantisReservationSpecific,
    OverviewletManager,
)
from seantis.reservation.mail_templates import templates
from seantis.reservation.reservations import (
    combine_reservations, CombinedReservations
)
from seantis.reservation.reserve import ReservationUrls


@grok.subscribe(IReservationsConfirmedEvent)
def on_reservations_confirmed(event):

    # send one mail to the reservee
    if settings.get('send_email_to_reservees'):
        send_reservations_confirmed(event.reservations, event.language)

    # send many mails to the admins
    if settings.get('send_email_to_managers') != 'never':
        for reservation in combine_reservations(event.reservations):

            if reservation.autoapprovable:
                send_reservation_mail(
                    reservation,
                    'reservation_made', event.language, to_managers=True
                )
            else:
                send_reservation_mail(
                    reservation,
                    'reservation_pending', event.language, to_managers=True
                )


@grok.subscribe(IReservationsApprovedEvent)
def on_reservations_approved(event):
    if not settings.get('send_email_to_reservees'):
        return
    if not event.reservation.autoapprovable:
        send_reservation_mail(
            event.reservations, 'reservation_approved', event.language
        )


@grok.subscribe(IReservationsDeniedEvent)
def on_reservations_denied(event):
    if not settings.get('send_email_to_reservees'):
        return
    if not event.reservation.autoapprovable:
        send_reservation_mail(
            event.reservations, 'reservation_denied', event.language
        )


@grok.subscribe(IReservationsRevokedEvent)
def on_reservations_revoked(event):
    if not settings.get('send_email_to_reservees'):
        return

    if not event.send_email:
        return

    send_reservation_mail(
        event.reservations, 'reservation_revoked', event.language,
        to_managers=False, reason=event.reason
    )


@grok.subscribe(IReservationTimeChangedEvent)
def on_reservation_time_changed(event):
    if not settings.get('send_email_to_reservees'):
        return

    if not event.send_email:
        return

    send_reservation_mail(
        [event.reservation], 'reservation_time_changed',
        event.language, to_managers=False, reason=event.reason,
        old_time=event.old_time, new_time=event.new_time
    )


class EmailTemplate(Item):
    def get_title(self):
        return _(u'Email Template') + u' ' + \
            utils.native_language_name(self.language)

    def set_title(self, title):
        pass

    title = property(get_title, set_title)


def get_managers_by_context(context):
    managers = context.users_with_local_role('Reservation-Manager')

    if managers:
        return managers

    if not hasattr(context, 'portal_type'):
        return []

    # if we arrive at the top level we just notify whoever got the reservation
    # manager role on the site
    if context.portal_type == 'Plone Site':
        return [
            m.id for m in
            getToolByName(context, 'portal_membership').listMembers()
            if m.has_role('Reservation-Manager')
        ]

    return get_managers_by_context(context.aq_inner.aq_parent)


def get_manager_emails_by_context(context):
    managers = get_managers_by_context(context)

    if not managers:
        return []

    acl = utils.getToolByName(context, 'acl_users')
    groups = acl.source_groups.getGroupIds()

    # remove the groups and replace them with users
    userids = []
    for man in managers:
        if man in groups:
            userids.extend(acl.source_groups.getGroupById(man).getMemberIds())
        else:
            userids.append(man)

    userids = set(userids)

    # go through the users and get their emails
    emails = []
    for uid in userids:
        user = acl.getUserById(uid)

        if user:
            emails.append(user.getProperty('email'))
        else:
            log.warn('The manager with the id %s does not exist' % uid)

    return emails


def get_manager_emails(context):
    if settings.get('send_email_to_managers') == 'by_path':
        return get_manager_emails_by_context(context)
    elif settings.get('send_email_to_managers') == 'by_address':
        return [settings.get('manager_email')]
    else:
        return []


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


def load_resources(reservations):
    resources = dict()

    for resource in (r.resource for r in reservations):
        if resource in resources:
            continue

        resources[resource] = utils.get_resource_by_uuid(resource).getObject()

    return resources


def may_send_mail(resource, mail, intended_for_admin):
    if intended_for_admin:
        return True

    if mail.recipient in get_manager_emails(resource):
        return False

    return True


def send_reservations_confirmed(reservations, language):

    sender = utils.get_site_email_sender()

    if not sender:
        log.warn('Cannot send email as no sender is configured')
        return

    # load resources
    resources = load_resources(reservations)

    # send reservations grouped by reservee email
    groupkey = lambda r: r.email
    by_recipient = groupby(sorted(reservations, key=groupkey), key=groupkey)

    for recipient, grouped_reservations in by_recipient:

        lines = []

        for reservation in combine_reservations(grouped_reservations):

            resource = resources[reservation.resource]

            prefix = '' if reservation.autoapprovable else '* '
            title_prefix = '{}x '.format(reservation.quota)
            lines.append(
                prefix + utils.get_resource_title(resource, title_prefix)
            )

            for start, end in reservation.timespans():
                lines.append(utils.display_date(start, end))

            lines.append('')

        # differs between resources
        subject, body = get_email_content(
            resource, 'reservation_received', language
        )

        mail = ReservationMail(
            resource, reservation,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            reservations=lines[:-1]
        )

        if may_send_mail(resource, mail, intended_for_admin=False):
            send_mail(resource, mail)


def send_reservation_mail(
    reservations, email_type, language, to_managers=False,
        reason=u'', old_time=None, new_time=None
):

    if isinstance(reservations, CombinedReservations):
        reservation = reservations
    else:
        reservation = tuple(combine_reservations(reservations))[0]

    resource = utils.get_resource_by_uuid(reservation.resource)

    # the resource doesn't currently exist in testing so we quietly
    # exit. This should be changed => #TODO
    if not resource:
        log.warn('Cannot send email as the resource does not exist')
        return

    sender = utils.get_site_email_sender()

    if not sender:
        log.warn('Cannot send email as no sender is configured')
        return

    resource = resource.getObject()

    if to_managers:
        recipients = get_manager_emails(resource)
        if not recipients:
            log.warn("Couldn't find a manager to send an email to")
            return
    else:
        recipients = [reservation.email]

    subject, body = get_email_content(resource, email_type, language)

    for recipient in recipients:
        mail = ReservationMail(
            resource, reservation,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            reason=reason,
            old_time=old_time,
            new_time=new_time
        )

        if may_send_mail(resource, mail, intended_for_admin=to_managers):
            send_mail(resource, mail)


def send_mail(context, mail):
    context.MailHost.send(mail.as_string(), immediate=False)


class ReservationMail(ReservationDataView, ReservationUrls):

    sender = u''
    recipient = u''
    subject = u''
    body = u''
    reservations = u''
    reason = u''
    old_time = None
    new_time = None

    def __init__(self, resource, reservation, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

        # get information for the body/subject string

        p = dict()
        is_needed = lambda key: key in self.subject or key in self.body

        # title of the resource
        if is_needed('resource'):
            p['resource'] = utils.get_resource_title(resource)

        # reservation email
        if is_needed('reservation_mail'):
            p['reservation_mail'] = reservation.email

        # a list of reservations
        if is_needed('reservations'):
            p['reservations'] = '\n'.join(self.reservations)

        # a list of dates
        if is_needed('dates'):
            lines = []
            dates = sorted(reservation.timespans(), key=lambda i: i[0])
            for start, end in dates:
                lines.append(utils.display_date(start, end))

            p['dates'] = '\n'.join(lines)

        # reservation quota
        if is_needed('quota'):
            p['quota'] = reservation.quota

        # tabbed reservation data
        if is_needed('data'):
            data = reservation.data
            lines = []
            for key in self.sort_reservation_data(data):
                interface = data[key]

                lines.append(interface['desc'])
                sorted_values = self.sort_reservation_data_values(
                    interface['values']
                )

                for value in sorted_values:
                    lines.append(
                        '\t' + value['desc'] + ': ' +
                        unicode(self.display_reservation_data(value['value']))
                    )

            p['data'] = '\n'.join(lines)

        if is_needed('reservation_link'):
            p['reservation_link'] = self.show_all_url(
                reservation.token, resource
            )

        # approval link
        if is_needed('approval_link'):
            p['approval_link'] = self.approve_all_url(
                reservation.token, resource
            )

        # denial link
        if is_needed('denial_link'):
            p['denial_link'] = self.deny_all_url(reservation.token, resource)

        # cancel link
        if is_needed('cancel_link'):
            p['cancel_link'] = self.revoke_all_url(reservation.token, resource)

        # revocation reason
        if is_needed('reason'):
            p['reason'] = self.reason

        # old time
        if is_needed('old_time'):
            p['old_time'] = utils.display_date(*self.old_time)

        # new time
        if is_needed('new_time'):
            p['new_time'] = utils.display_date(*self.new_time)

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
        msg = utils.translate(
            context, request,
            _(u"There's already an Email template in the same folder for the "
              u"same language")
        )
        utils.form_error(msg)


class TemplateAddForm(dexterity.AddForm):

    permission = 'cmf.AddPortalContent'

    grok.context(IEmailTemplate)
    grok.require(permission)
    grok.layer(ISeantisReservationSpecific)

    grok.name('seantis.reservation.emailtemplate')

    def update(self, **kwargs):
        super(TemplateAddForm, self).update(**kwargs)
        self.use_translated_emails_as_default()

    def get_field_map(self, suffix):
        return dict(
            (field.replace(suffix, ''), field)
            for field in getFields(self.schema) if field.endswith(suffix)
        )

    def apply_field_map(self, mapping, get_template_value):
        for template, field in mapping.items():
            value = get_template_value(template)
            if value:
                self.widgets[field].value = value

    def use_translated_emails_as_default(self):
        language = utils.get_current_language(self.context, self.request)[:2]

        subjects = self.get_field_map('_subject')
        contents = self.get_field_map('_content')

        self.apply_field_map(
            subjects, lambda tpl: templates[tpl].get_subject(language)
        )
        self.apply_field_map(
            contents, lambda tpl: templates[tpl].get_body(language)
        )

    @button.buttonAndHandler(_('Save'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        validate_template(self.context, self.request, data)
        dexterity.AddForm.handleAdd(self, action)


class TemplateEditForm(dexterity.EditForm):

    permission = 'cmf.ModifyPortalContent'

    grok.context(IEmailTemplate)
    grok.require(permission)
    grok.layer(ISeantisReservationSpecific)

    @button.buttonAndHandler(_(u'Save'), name='save')
    def handleApply(self, action):
        data, errors = self.extractData()
        validate_template(self.context, self.request, data)
        dexterity.EditForm.handleApply(self, action)


class TemplatesViewlet(BaseViewlet):

    permission = 'cmf.ModifyPortalContent'

    grok.context(IFolderish)
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
            return [(
                _(u'Add email template'),
                baseurl + '/++add++seantis.reservation.emailtemplate'
            )]

        # template specific links
        links = []

        baseurl = template.absolute_url()
        links.append((_(u'Edit'), baseurl + '/edit'))
        links.append((_(u'Delete'), baseurl + '/delete_confirmation'))

        return links

    def render(self, **kwargs):
        return self._template.render(self)
