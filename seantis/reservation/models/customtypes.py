import uuid
import json

from seantis.reservation import utils

from sqlalchemy.types import TypeDecorator, CHAR, TEXT
from sqlalchemy.dialects.postgresql import UUID


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value)
            else:
                # hexstring
                return "%.32x" % value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict()

    """

    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value, cls=utils.UserFormDataEncoder)

        return value

    def process_result_value(self, value, dialect):
        def object_hook(dictionary):
            for key, value in dictionary.items():
                if isinstance(value, basestring):
                    dictionary[key] = utils.userformdata_decode(value)
                elif isinstance(value, (list, tuple)):
                    dictionary[key] = map(utils.userformdata_decode, value)

            return dictionary

        if value is not None:
            value = json.loads(value, object_hook=object_hook)
        return value
