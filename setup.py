from setuptools import setup, find_packages
import os

name = "seantis.reservation"
description = "Plone addon to reserve stuff in a calendar."
version = '1.0'

zug_require = [
    'izug.basetheme',
    'ftw.contentmenu'
]


def get_long_description():
    readme = open('README.rst').read()
    history = open(os.path.join('docs', 'HISTORY.txt')).read()

    # cut the part before the description to avoid repetition on pypi
    readme = readme[readme.index(description) + len(description):]

    return '\n'.join((readme, history))

setup(name=name, version=version, description=description,
      long_description=get_long_description(),
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
