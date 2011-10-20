import os
import tempfile

from App.config import getConfiguration, setConfiguration
from plone.app.testing import PloneSandboxLayer 
from plone.app.testing import PLONE_FIXTURE 
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.testing import z2
from zope.configuration import xmlconfig 

class SeantisReservation(PloneSandboxLayer):
    default_bases = (PLONE_FIXTURE,)

    def setUpConfig(self):
        fileno, self.dbFileName = tempfile.mkstemp(suffix='.db')
        dsn = 'sqlite:///%s' % self.dbFileName

        config = getConfiguration()
        if not hasattr(config, 'product_config'):
            config.product_config = {}
        
        config.product_config['seantis.reservation'] = dict(dsn=dsn)

        setConfiguration(config)

    def setUpDatabase(self):
        from seantis.reservation import setuphandlers
        setuphandlers.dbsetup(None)

    def setUpZope(self, app, configurationContext):

        self.setUpConfig()

        import seantis.reservation
        xmlconfig.file('configure.zcml',
            seantis.reservation, 
            context=configurationContext
        )

        self.setUpDatabase()

        z2.installProduct(app, 'seantis.reservation')

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'seantis.reservation')
        os.unlink(self.dbFileName)

SEANTIS_RESERVATION_FIXTURE = SeantisReservation()

SEANTIS_RESERVATION_INTEGRATION_TESTING = IntegrationTesting(
        bases=(SEANTIS_RESERVATION_FIXTURE, ),
        name="SeantisReservation:Integration"
    )

SEANTIS_RESERVATION_FUNCTIONAL_TESTING = FunctionalTesting(
        bases=(SEANTIS_RESERVATION_FIXTURE, ),
        name="SeantisReservation:Functional"
    )