from seantis.reservation import plone_session
from seantis.reservation.tests import IntegrationTestCase


class TestPloneSession(IntegrationTestCase):

    def test_get_session(self):
        context = self.portal
        result = plone_session.get_session(context, 'test')
        self.assertEqual(None, result)

        plone_session.set_session(context, 'test', 'data')
        result = plone_session.get_session(context, 'test')
        self.assertEqual('data', result)

    def test_session_key(self):
        portal_id = self.portal.id
        result = plone_session.session_key('test')
        self.assertEqual('%s:reservation:test' % portal_id, result)

    def test_get_mail(self):
        context = self.portal
        result = plone_session.get_email(context)
        self.assertEqual(None, result)

        plone_session.set_email(context, 'info@seantis.ch')
        result = plone_session.get_email(context)
        self.assertEqual('info@seantis.ch', result)

    def test_get_additional_data(self):
        context = self.portal
        result = plone_session.get_additional_data(context)
        self.assertEqual(None, result)

        plone_session.set_additional_data(context, 'test data')
        result = plone_session.get_additional_data(context)
        self.assertEqual('test data', result)

    def test_get_session_id(self):
        context = self.portal
        result1 = plone_session.get_session_id(context)
        result2 = plone_session.get_session_id(context)
        self.assertEqual(result1, result2)
