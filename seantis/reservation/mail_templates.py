import logging
import codecs
from os import path

logger = logging.getLogger('seantis.reservation')
folder = path.join(path.dirname(path.abspath(__file__)), 'emails')


def get_filename(key, language):
    filename = '%s.%s.txt' % (key, language)
    return path.join(folder, filename)


class MailTemplate(object):

    def __init__(self, template):
        self.templates = dict()
        self.key = template
        assert self.is_translated('en')

    def is_translated(self, language):
        return path.exists(get_filename(self.key, language))

    def load_language(self, language):
        with codecs.open(get_filename(self.key, language), "r", "utf-8") as f:
            self.templates[language] = self.parse_file(f)

        return self.templates[language]

    def get(self, language):

        if language in self.templates:
            return self.templates[language]

        if self.is_translated(language):
            return self.load_language(language)

        logger.warning(
            'Email template for language %s does not exist', language
        )

        return self.get('en')

    def get_subject(self, language):
        return self.get(language)[0]

    def get_body(self, language):
        return self.get(language)[1]

    def parse_file(self, template_file):

        subject = u''
        body = []

        for line in (l.strip('\n\t') for l in template_file):

            if line.startswith('#'):
                continue

            if not subject:
                subject = line
                continue

            if subject and not body and line.startswith('='):
                continue

            body.append(line)

        return unicode(subject), unicode('\n'.join(body))

keys = [
    'reservation_approved',
    'reservation_pending',
    'reservation_received',
    'reservation_denied',
    'reservation_revoked',
    'reservation_made',
    'reservation_time_changed'
]

templates = dict([(k, MailTemplate(k)) for k in keys])
