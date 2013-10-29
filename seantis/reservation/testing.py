from App.config import getConfiguration, setConfiguration
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.app.testing import applyProfile
from plone.app.testing import quickInstallProduct
from plone.testing import z2
from Testing import ZopeTestCase

try:
    from seantis.reservation import test_database
except ImportError:
    from seantis.reservation.utils import ConfigurationError
    msg = 'No test database configured in seantis.reservation.test_database.'
    raise ConfigurationError(msg)


class SqlLayer(PloneSandboxLayer):

    default_bases = (PLONE_FIXTURE,)

    class Session(dict):
        def set(self, key, value):
            self[key] = value

    @property
    def dsn(self):
        if not self.get('dsn'):
            self['dsn'] = test_database.testdsn

        return self['dsn']

    def init_config(self):
        config = getConfiguration()
        if not hasattr(config, 'product_config'):
            config.product_config = {}

        config.product_config['seantis.reservation'] = dict(dsn=self.dsn)

        setConfiguration(config)

    def setUpZope(self, app, configurationContext):

        # Set up sessioning objects
        app.REQUEST['SESSION'] = self.Session()
        ZopeTestCase.utils.setupCoreSessions(app)

        self.init_config()

        import seantis.reservation
        self.loadZCML(package=seantis.reservation)

        # treat certain sql warnings as errors
        import warnings
        warnings.filterwarnings('error', 'The IN-predicate.*')
        warnings.filterwarnings('error', 'Unicode type received non-unicode.*')

    def setUpPloneSite(self, portal):

        quickInstallProduct(portal, 'plone.app.dexterity')
        quickInstallProduct(portal, 'seantis.reservation')
        quickInstallProduct(portal, 'plone.formwidget.datetime')
        quickInstallProduct(portal, 'plone.formwidget.recurrence')
        applyProfile(portal, 'seantis.reservation:default')

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'seantis.reservation')

SQL_FIXTURE = SqlLayer()

SQL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(SQL_FIXTURE, ),
    name="SqlLayer:Integration"
)

SQL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(SQL_FIXTURE, ),
    name="SqlLayer:Functional"
)
