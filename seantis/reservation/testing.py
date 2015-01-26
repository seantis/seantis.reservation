from __future__ import absolute_import

from App.config import getConfiguration, setConfiguration
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.app.testing import applyProfile
from plone.app.testing import quickInstallProduct
from plone.testing import z2
from Testing import ZopeTestCase
from testing.postgresql import Postgresql
from zope.configuration import xmlconfig


class SqlLayer(PloneSandboxLayer):

    default_bases = (PLONE_FIXTURE,)

    class Session(dict):
        def set(self, key, value):
            self[key] = value

    def start_postgres(self):
        self.postgres = Postgresql()
        return self.postgres.url().replace(
            'postgresql://', 'postgresql+psycopg2://')

    def stop_postgres(self):
        self.postgres.stop()

    def init_config(self, dsn):
        config = getConfiguration()
        if not hasattr(config, 'product_config'):
            config.product_config = {}

        config.product_config['seantis.reservation'] = dict(dsn=dsn)

        setConfiguration(config)

    def setUpZope(self, app, configurationContext):

        # Set up sessioning objects
        app.REQUEST['SESSION'] = self.Session()
        ZopeTestCase.utils.setupCoreSessions(app)

        self.init_config(dsn=self.start_postgres())

        import seantis.reservation
        xmlconfig.file(
            'configure.zcml',
            seantis.reservation,
            context=configurationContext
        )
        self.loadZCML(package=seantis.reservation)

    def setUpPloneSite(self, portal):

        quickInstallProduct(portal, 'plone.app.dexterity')
        quickInstallProduct(portal, 'seantis.reservation')
        applyProfile(portal, 'seantis.reservation:default')

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'seantis.reservation')
        self.stop_postgres()

SQL_FIXTURE = SqlLayer()

SQL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(SQL_FIXTURE, ),
    name="SqlLayer:Integration"
)

SQL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(SQL_FIXTURE, ),
    name="SqlLayer:Functional"
)
