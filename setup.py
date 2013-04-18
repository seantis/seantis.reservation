from setuptools import setup, find_packages
import os

version = '1.0b4'

zug_require = [
    'izug.basetheme',
    'ftw.contentmenu'
]

setup(name='seantis.reservation',
      version=version,
      description="Reservation system for plone portal types",
      long_description=('\n'.join((
          open("README.md").read(),
          open(os.path.join("docs", "HISTORY.txt")).read()
      ))),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
          "Framework :: Plone",
          "Programming Language :: Python",
      ],
      keywords='Reservation, Calendar, Zug, Seantis',
      author='Seantis GmbH',
      author_email='info@seantis.ch',
      url='http://svn.plone.org/svn/collective/',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['seantis'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'Plone>=4.1.4',
          'plone.uuid>=1.0.2',
          'setuptools',
          'psycopg2',
          'SQLAlchemy>=0.7.3',
          'zope.sqlalchemy',
          'collective.autopermission',
          'collective.testcaselayer',
          'plone.app.testing',
          'plone.app.dexterity [grok]',
          'plone.behavior',
          'plone.directives.form',
          'plone.app.referenceablebehavior',
          'collective.js.jqueryui',
          'collective.js.underscore',
          'collective.js.fullcalendar>=1.6.1',
          'profilehooks',
          'pytz',
          'ordereddict',
          'alembic',
          'xlwt',
          'tablib',
          'mock',
          'isodate',
      ],
      zug_require=zug_require,
      extras_require=dict(zug=zug_require),
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      setup_requires=["PasteScript"],
      paster_plugins=["ZopeSkel"],
      )
