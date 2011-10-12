from setuptools import setup, find_packages
import os

version = '0.1'

setup(name='seantis.reservation',
      version=version,
      description="Reservation system for plone portal types",
      long_description=open("README.md").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
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
          'Plone',
          'setuptools',
          'z3c.saconfig',
          'psycopg2',
          'collective.autopermission',
          'collective.testcaselayer',
          'plone.app.testing',
          'plone.app.dexterity [grok]',
          'plone.behavior',
          'plone.directives.form',
          'plone.app.referenceablebehavior',
          'collective.js.jqueryui',
          'collective.js.underscore'
      ],
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      setup_requires=["PasteScript"],
      paster_plugins=["ZopeSkel"],
      )
