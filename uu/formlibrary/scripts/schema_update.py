"""
schema_update.py -- update schemas when plone.supermodel serialization
                    changes may affect signatures (usually after Plone
                    upgrades).

USE this as a runscript via ./bin/instance run ...
"""

from AccessControl.SecurityManagement import newSecurityManager
from Acquisition import aq_base
from Products.CMFCore.utils import getToolByName
import transaction
from zope.component.hooks import setSite
from zope.component import queryUtility

from uu.dynamicschema.interfaces import ISchemaSaver, DEFAULT_MODEL_XML
from uu.formlibrary.handlers import definition_schema_handler
from uu.formlibrary.interfaces import DEFINITION_TYPE, IFormSet
from uu.formlibrary.interfaces import IMultiForm, ISimpleForm
from uu.formlibrary.utils import local_query

SITES = ('qiteamspace', 'cnhnqi', 'opip', 'maine')
VHOSTBASE = '/VirtualHostBase/https/teamspace1.upiq.org'


def migrate_definition_schema(definition):
    definition_schema_handler(definition, None)  # will load, then reserialize


def verify(definition, saver, wftool):
    # verify that definition signature matches schema
    computed = saver.signature(definition.schema)
    assert computed == definition.signature
    # verify schema in saver
    assert computed in saver
    # verify serialize/load round-trip for schema saving
    assert saver.signature(saver.load(saver.get(computed))) == computed
    # verify that all form entries are signed with same signature
    forms = IFormSet(definition).values()
    for form in forms:
        blocked_states = ('published', 'archived')
        if wftool.getInfoFor(form, 'review_state') in blocked_states:
            continue   # archived or published form, ignore as preserved
        if IMultiForm.providedBy(form):
            records = form.values()
            assert all(map(lambda v: v.signature == computed, records))
        if ISimpleForm.providedBy(form):
            pass  # TODO


def migrate_schemas(site):
    saver = queryUtility(ISchemaSaver)
    wftool = getToolByName(site, 'portal_workflow')
    migrated = []
    formcount = 0
    q = {'portal_type': DEFINITION_TYPE}
    results = site.portal_catalog.unrestrictedSearchResults(q)
    for brain in results:
        definition = brain._unrestrictedGetObject()
        core = aq_base(definition)
        if not hasattr(core, 'entry_schema'):
            core.entry_schema = DEFAULT_MODEL_XML
        migrate_definition_schema(definition)
        migrated.append(definition)
        formcount += len(IFormSet(definition))
        print '\t  Migrated definition %s' % (
            '/'.join(definition.getPhysicalPath()),
            )
        verify(definition, saver, wftool)
    print '\t-- Migrated %s definitions (%s total forms)' % (
        len(migrated),
        formcount,
        )


def main(app):
    user = app.acl_users.getUser('admin')
    newSecurityManager(None, user)
    for name in SITES:
        print '== SITE: %s ==' % name
        site = app[name]
        setSite(site)
        migrate_schemas(site)
        txn = transaction.get()
        txn.note('%s%s' % (VHOSTBASE, '/'.join(site.getPhysicalPath())))
        txn.note('Migrated schemas to plone.supermodel 1.2.6 syntax')
        txn.commit()


if __name__ == '__main__':
    main(app)   # noqa

