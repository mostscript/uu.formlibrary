from setuptools import setup, find_packages
import os

version = '0.1dev'

setup(name='uu.formlibrary',
      version=version,
      description="Plone add-on for form definitions and form instances.",
      long_description=open("README.txt").read() + "\n" +
                       open("CHANGES.txt").read(),
      classifiers=[
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Framework :: Plone",
        "Framework :: Zope2",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        ],
      keywords='',
      author='Sean Upton',
      author_email='sean.upton@hsc.utah.edu',
      url='http://launchpad.net/upiq',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['uu'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'zope.schema>=3.8.0',
          'collective.z3cform.datagridfield>=0.9',
          'plone.app.dexterity',
          'plone.uuid',
          'plone.alterego',
          'plone.supermodel',
          'plone.synchronize',
          'plone.schemaeditor>=1.0',
          'plone.app.linkintegrity',
          'zope.globalrequest',
          'zope.app.testing', #for z3c.form.testing requirement
          'Products.CMFPlone',
          'uu.workflows',
          'uu.record',
          'uu.dynamicschema',
          'uu.retrieval',
          'uu.smartdate',
          # -*- Extra requirements: -*-
      ],
      extras_require = {
          'test': [ 'plone.app.testing>=4.0', ],
      },
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )

