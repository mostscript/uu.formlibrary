from datetime import datetime

import transaction
from zope.component.hooks import setSite
from zope.component import queryUtility

from uu.dynamicschema.interfaces import ISchemaSaver, DEFAULT_SIGNATURE
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE
from uu.formlibrary.interfaces import IDefinitionBase, IFormSet
from uu.formlibrary.interfaces import IMultiForm, IFormDefinition


PKGNAME = 'uu.formlibrary'
BASEPATH = '/VirtualHostBase/https/teamspace1.upiq.org'

TYPEQUERY = {
    'portal_type': {
        'query': (DEFINITION_TYPE, FIELD_GROUP_TYPE),
        'operator': 'or',
        }
    }

_installed = lambda site: site.portal_quickinstaller.isProductInstalled
product_installed = lambda site, name: _installed(site)(name)

search = lambda site, q: site.portal_catalog.unrestrictedSearchResults(q)
get = lambda brain: brain._unrestrictedGetObject()


def commit(context, msg):
    txn = transaction.get()
    # Undo path, if you want to use it, unfortunately is site-specific,
    # so use the hostname used to access all Plone sites.
    txn.note('%s%s' % (BASEPATH, '/'.join(context.getPhysicalPath())))
    txn.note(msg)
    txn.commit()


def form_signature(form, definition):
    if IMultiForm.providedBy(form) and len(form):
        return form.values()[0].signature
    return definition.signature  # fallback for form with no records


def all_forms_signatures(definition):
    forms = IFormSet(definition).values()
    return set(form_signature(form, definition) for form in forms)


def verify(site):
    """Verify that nothing we need is gone!"""
    actively_used = set([DEFAULT_SIGNATURE])
    saver = queryUtility(ISchemaSaver)
    schema_contexts = map(get, search(site, TYPEQUERY))
    definitions = filter(IFormDefinition.providedBy, schema_contexts)
    actively_used.update(o.signature for o in schema_contexts)
    current = len(actively_used)
    actively_used.update(
        *[all_forms_signatures(defn) for defn in definitions]
        )
    archived = len(actively_used) - current
    # sufficient:
    for signature in actively_used:
        assert signature in saver
    # only necessary: counts of schemas in saver should match actively_used
    assert len(saver) == len(actively_used)
    if archived:
        print '\t\tNote: %s schemas preserved for archival.' % archived


def cleanup_stored_schemas(site):
    print '\t=== SITE: %s ===' % site.getId()
    # get schema saver:
    saver = queryUtility(ISchemaSaver)
    size_before = len(saver)
    # calculate in-use schema signatures:
    actively_used = set()  # in-use md5 schema signatures
    content = map(get, search(site, TYPEQUERY))
    for context in content:
        assert IDefinitionBase.providedBy(context)
        assert context.signature is not None
        # consider the current schema (signature) used now by definition
        # or field group in question:
        actively_used.add(context.signature)
        if IFormDefinition.providedBy(context):
            # consider any past schema signatures on records now marked as
            # having schema immutability when definition is modified:
            actively_used.update(all_forms_signatures(context))
    # enumerate through schema saver:
    for signature in list(saver.keys()):
        if signature == DEFAULT_SIGNATURE:
            continue  # leave this alone, attempting to remove --> exception
        if signature not in actively_used:
            del(saver[signature])
    size_after = len(saver)
    removed = size_before - size_after
    if removed:
        print (
            '\t\tRemoved %s (of %s) orphaned schemas from local storage.' % (
                removed,
                size_before,
                )
            )
        verify(site)
        commit(site, 'Cleaned up orphaned schemas')


def main(app):
    print '== Schema cleanup: %s' % str(datetime.now())
    for site in app.objectValues('Plone Site'):
        setSite(site)
        if product_installed(site, PKGNAME):
            cleanup_stored_schemas(site)


if __name__ == '__main__' and 'app' in locals():
    main(app)   # noqa

