from zope.i18nmessageid import MessageFactory
_ = MessageFactory('seantis.reservation')

from session import Session, db

# Pyflakes
Session
db
