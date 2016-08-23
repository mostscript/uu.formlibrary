from setuptools import setup, find_packages

version = '0.9.dev0'

setup(
    name='uu.formlibrary',
    version=version,
    description="Plone add-on for form definitions and form instances.",
    long_description=(
        open("README.txt").read() + "\n" +
        open("CHANGES.txt").read()
        ),
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
    url='http://github.com/upiq',
    license='GPL',
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['uu'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',
        'zope.schema>=3.8.0',
        'collective.z3cform.datagridfield>=0.9',
        'collective.z3cform.datetimewidget',
        'plone.app.dexterity',
        'plone.app.widgets<2.0',
        'plone.uuid',
        'plone.alterego',
        'plone.supermodel',
        'plone.synchronize',
        'plone.schemaeditor>=1.0',
        'plone.app.linkintegrity',
        'plone.app.textfield',
        'plone.app.widgets<2.0',
        'zope.globalrequest',
        'zope.app.testing',  # for z3c.form.testing requirement
        'Products.CMFPlone',
        'uu.workflows',
        'uu.record',
        'uu.dynamicschema',
        'uu.retrieval',
        # -*- Extra requirements: -*-
    ],
    extras_require = {
        'test': ['plone.app.testing>=4.0'],
    },
    entry_points="""
    # -*- Entry points: -*-
    [z3c.autoinclude.plugin]
    target = plone
    """,
    )

