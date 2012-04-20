import logging
import codecs
from os import path

logger = logging.getLogger('seantis.reservation')
folder = path.join(path.dirname(path.abspath(__file__)), 'mail_templates')

def get_filename(key, language):
    filename = '%s.%s.txt' % (key, language)
    return path.join(folder, filename)

class MailTemplate(object):

    templates = {}

    def __init__(self, template):
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

        logger.warning('Email template for language %s does not exist', language)

        return self.get('en')

    def get_subject(self, language):
        return self.get(language)[0]

    def get_content(self, language):
        return self.get(language)[1]

    def parse_file(self, template_file):
        
        subject = u''
        content = []

        for line in (l.strip('\n\t') for l in template_file):

            if line.startswith('#'):
                continue
            
            if not subject:
                subject = line
                continue

            if subject and not content and line.startswith('='):
                continue

            content.append(line)

        return unicode(subject), unicode('\n'.join(content))

keys = [
    'reservation_approved',
    'reservation_pending',
    'reservation_autoapproved',
    'reservation_received',
    'reservation_denied'
]

templates = dict([(k, MailTemplate(k)) for k in keys])