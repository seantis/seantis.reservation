from textwrap import dedent

from datetime import date, datetime, timedelta

from seantis.reservation import utils
from seantis.reservation import settings
from seantis.reservation.error import CustomReservationError
from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.restricted_eval import (
    validate_expression,
    evaluate_expression,
    run_pre_reserve_script
)


class TestCustomFilterScript(IntegrationTestCase):

    def test_restricted_validate(self):
        run = lambda script: validate_expression(dedent(script), 'exec')

        # wrong syntax
        script = """
        if True
            pass
        """
        self.assertRaises(SyntaxError, run, script)

        # disallowed opcode
        script = """
        class Test(object):
            pass
        """
        self.assertRaises(ValueError, run, script)

    def test_restricted_evaluate(self):
        run = lambda s, g=None, l=None: evaluate_expression(
            dedent(s), g, l, 'exec'
        )

        script = "file = open('x')"
        self.assertRaises(NameError, run, script)

        locals_ = {}
        run(script, g={'open': lambda x: 'foo'}, l=locals_)
        self.assertEqual(locals_['file'], 'foo')

        run("file = var", g={'var': 'test'}, l=locals_)
        self.assertEqual(locals_['file'], 'test')

    def test_pre_reserve_script_variables(self):

        class MockContext(object):
            def getPhysicalPath(self):
                return ['', 'foo', 'bar']

        start, end = datetime.now(), datetime.now()
        data = utils.mock_data_dictionary({
            'is_test': True,
            'description': 'This is the description'
        })

        settings.set('pre_reservation_script', u'exit()')

        locals_ = {}
        run_pre_reserve_script(MockContext(), start, end, data, locals_)

        self.assertEqual(locals_['path'], '/foo/bar')
        self.assertFalse(locals_['is_group_reservation'])
        self.assertEqual(locals_['start'], start)
        self.assertEqual(locals_['end'], end)
        self.assertEqual(locals_['date'], date)
        self.assertEqual(locals_['datetime'], datetime)
        self.assertEqual(locals_['timedelta'], timedelta)
        self.assertTrue(locals_['formset_available']('mock'))

    def test_pre_reserve_script_example(self):

        class MockContext(object):
            def getPhysicalPath(self):
                return ['', 'foo', 'bar']

        script = u"""
        if is_group_reservation:
            exit()

        if not formset_available('personalien'):
            exit()

        if personalien.zipcode != '1337':
            error('People with uncool zipcodes are not welcome.')
        """

        settings.set('pre_reservation_script', dedent(script))

        start, end = None, None
        data = utils.mock_data_dictionary({})

        run = lambda: run_pre_reserve_script(MockContext(), start, end, data)

        run()  # exits early because it's a group reservation

        start, end = datetime.now(), datetime.now()

        run()  # exits early because the formset is not available

        data = utils.mock_data_dictionary({
            'zipcode': '1234'
        }, 'personalien')

        self.assertRaises(CustomReservationError, run)  # uncool zipcode

        data = utils.mock_data_dictionary({
            'zipcode': '1337'
        }, 'personalien')

        run()  # ok
