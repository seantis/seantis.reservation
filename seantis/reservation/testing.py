import os
import tempfile
import sqlalchemy

from z3c.saconfig.utility import EngineFactory
from z3c.saconfig.utility import GloballyScopedSession

from plone.app.testing import PloneSandboxLayer 
from plone.app.testing import PLONE_FIXTURE 
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting

from plone.testing import z2

from zope.component import provideUtility
from zope.configuration import xmlconfig 

class SeantisReservation(PloneSandboxLayer):
    default_bases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        import seantis.reservation
        xmlconfig.file('configure.zcml',
            seantis.reservation, 
            context=configurationContext
        ) 

        z2.installProduct(app, 'seantis.reservation')

        fileno, self.dbFileName = tempfile.mkstemp(suffix='.db')
        dbURI = 'sqlite:///%s' % self.dbFileName
        dbEngine = sqlalchemy.create_engine(dbURI)
        seantis.reservation.ORMBase.metadata.create_all(dbEngine)

        engine = EngineFactory(dbURI, echo=False, convert_unicode=False)
        provideUtility(engine, name=u'ftesting')
        session = GloballyScopedSession(engine=u'ftesting', twophase=False)
        provideUtility(session)

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