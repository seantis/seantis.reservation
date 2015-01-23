# -*- coding: utf-8 -*-

import functools
import six
import sys

from logging import getLogger
log = getLogger('seantis.reservation')

from datetime import date, datetime, timedelta

from byteplay import (
    Code, Opcode,
    POP_TOP, ROT_TWO, ROT_THREE, ROT_FOUR, DUP_TOP, DUP_TOPX,
    POP_BLOCK, SETUP_LOOP, BUILD_LIST, BUILD_MAP, BUILD_TUPLE,
    LOAD_CONST, RETURN_VALUE, STORE_SUBSCR, STORE_MAP,
    UNARY_POSITIVE, UNARY_NEGATIVE, UNARY_NOT,
    UNARY_INVERT, BINARY_POWER, BINARY_MULTIPLY,
    BINARY_DIVIDE, BINARY_FLOOR_DIVIDE, BINARY_TRUE_DIVIDE,
    BINARY_MODULO, BINARY_ADD, BINARY_SUBTRACT, BINARY_SUBSCR,
    BINARY_LSHIFT, BINARY_RSHIFT, BINARY_AND, BINARY_XOR,
    BINARY_OR, INPLACE_ADD, INPLACE_SUBTRACT, INPLACE_MULTIPLY,
    INPLACE_DIVIDE, INPLACE_POWER,
    INPLACE_LSHIFT, INPLACE_RSHIFT, INPLACE_AND,
    INPLACE_XOR, INPLACE_OR, LOAD_NAME, CALL_FUNCTION, COMPARE_OP, LOAD_ATTR,
    STORE_NAME, GET_ITER, FOR_ITER, LIST_APPEND, DELETE_NAME,
    JUMP_FORWARD, POP_JUMP_IF_TRUE, JUMP_ABSOLUTE,
    JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP,
    MAKE_FUNCTION, SLICE_0, SLICE_1, SLICE_2, SLICE_3,
    POP_JUMP_IF_FALSE,
    SETUP_EXCEPT, END_FINALLY
)

import seantis.reservation

from seantis.reservation import utils
from seantis.reservation.error import CustomReservationError

allowed_op_codes = set([
    POP_TOP, ROT_TWO, ROT_THREE, ROT_FOUR, DUP_TOP, DUP_TOPX,
    POP_BLOCK, SETUP_LOOP, BUILD_LIST, BUILD_MAP, BUILD_TUPLE,
    LOAD_CONST, RETURN_VALUE, STORE_SUBSCR, STORE_MAP,
    UNARY_POSITIVE, UNARY_NEGATIVE, UNARY_NOT,
    UNARY_INVERT, BINARY_POWER, BINARY_MULTIPLY,
    BINARY_DIVIDE, BINARY_FLOOR_DIVIDE, BINARY_TRUE_DIVIDE,
    BINARY_MODULO, BINARY_ADD, BINARY_SUBTRACT, BINARY_SUBSCR,
    BINARY_LSHIFT, BINARY_RSHIFT, BINARY_AND, BINARY_XOR,
    BINARY_OR, INPLACE_ADD, INPLACE_SUBTRACT, INPLACE_MULTIPLY,
    INPLACE_DIVIDE, INPLACE_POWER,
    INPLACE_LSHIFT, INPLACE_RSHIFT, INPLACE_AND,
    INPLACE_XOR, INPLACE_OR, LOAD_NAME, CALL_FUNCTION, COMPARE_OP, LOAD_ATTR,
    STORE_NAME, GET_ITER, FOR_ITER, LIST_APPEND, DELETE_NAME,
    JUMP_FORWARD, POP_JUMP_IF_TRUE, POP_JUMP_IF_FALSE, JUMP_ABSOLUTE,
    JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP,
    MAKE_FUNCTION, SLICE_0, SLICE_1, SLICE_2, SLICE_3,
    JUMP_IF_FALSE_OR_POP, JUMP_IF_TRUE_OR_POP, POP_JUMP_IF_FALSE,
    POP_JUMP_IF_TRUE, SETUP_EXCEPT, END_FINALLY
])


def validate_expression(expression, mode='eval'):
    try:
        code = compile(expression, '<dynamic>', mode)
    except (SyntaxError, TypeError):
        raise

    used_codes = set(
        i[0] for i in Code.from_code(code).code if isinstance(i[0], Opcode)
    )

    for opcode in used_codes:
        if opcode not in allowed_op_codes:

            raise ValueError("{} is not an allowed opcode".format(opcode))

    return code


def evaluate_expression(expression, globals_=None, locals_=None, mode='eval'):
    globals_ = globals_ if globals_ is not None else {}
    locals_ = locals_ if locals_ is not None else {}

    globals_.update(
        __builtins__={
            'True': True,
            'False': False,
            'None': None,
            'str': str,
            'globals': locals,
            'locals': locals,
            'bool': bool,
            'dict': dict,
            'list': list,
            'tuple': tuple,
            'map': map,
            'abs': abs,
            'min': min,
            'max': max,
            'reduce': functools.reduce,
            'filter': filter,
            'round': round,
            'len': len,
            'set': set
        }
    )

    code = validate_expression(expression, mode=mode)
    return eval(code, globals_, locals_)


def run_pre_reserve_script(context, start, end, data, locals_=None):
    """ Runs the python script found in the seantis reservation settings
    under a restricted environment with only a selected number of functions
    and variables available.

    The script is able to validate the reservation before it is done,
    giving the ability to implement very specific validation requirements
    of customers with custom fields.

    Obviously this script can't be testet and is insecure by nature. So it
    should be used sparingly and with caution.

    The available methods and variables are purposely undocumented on the
    user interface, because it's meant for developers, not users.
    """
    script = seantis.reservation.settings.get('pre_reservation_script')
    script = isinstance(script, six.string_types) \
        and six.text_type(script) or u''
    script = script.strip()

    if not script:
        return

    errors = []

    locals_ = locals_ if locals_ is not None else {}
    locals_.update({
        'path': '/'.join(context.getPhysicalPath()),
        'is_group_reservation': not(start and end),
        'start': start,
        'end': end,
        'date': date,
        'datetime': datetime,
        'timedelta': timedelta,
        'error': errors.append,
        'exit': sys.exit,
        'log': log,
        'formset_available': lambda formset: formset in data
    })
    locals_.update(utils.additional_data_objects(data))

    try:
        evaluate_expression(script, locals_=locals_, mode='exec')
    except SystemExit:
        return
    if errors:
        raise CustomReservationError(errors[0])
