from setuptools import setup, find_packages
import os

version = '1.0'

zug_require = [
    'izug.basetheme',
    'ftw.contentmenu'
]

setup(name='seantis.reservation',
      version=version,
      description="Reservation system for plone portal types",
      long_description=('\n'.join((
          open("README.rst").read(),
          open(os.path.join("docs", "HISTORY.txt")).read()
      ))),
      classifiers=[
          'Framework :: Plone',
          'Framework :: Plone :: 4.3',
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Programming Language :: Python',
      ],
      keywords='reservation calendar seantis plone dexterity',
      author='Seantis GmbH',
      author_email='info@seantis.ch',
      url='https://github.com/seantis/seantis.reservation',
      license='GPL v2',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['seantis'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'Plone>=4.3',
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
          'alembic>=0.5.0',
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
      """
      )
