import sys

import transaction
from zope.component.hooks import setSite

PKGNAME = 'uu.formlibrary'
PROFILE = 'profile-%s:default' % PKGNAME


_installed = lambda site: site.portal_quickinstaller.isProductInstalled
product_installed = lambda site, name: _installed(site)(name)


def stale_catalog_entries(site, catalog=None):
    stale = []
    catalog = catalog or site.portal_catalog
    _catalog = catalog._catalog
    getbrain = lambda rid: _catalog[rid]
    getobject = lambda brain: brain._unrestrictedGetObject()
    for rid, path in list(_catalog.paths.items()):
        brain = getbrain(rid)
        try:
            o = getobject(brain)  # noqa, poking for exception
        except KeyError:
            print 'Stale path (%s): %s' % (rid, path)
            stale.append((rid, path))
    return stale


def prune_stale_catalog_entries(site):
    catalog = site.portal_catalog
    stale = stale_catalog_entries(site, catalog)
    _catalog = catalog._catalog
    for rid, path in stale:
        if rid in _catalog.data:
            del(_catalog.data[rid])
        if rid in _catalog.paths:
            del(_catalog.paths[rid])
        if path in _catalog.uids:
            del(_catalog.uids[path])
    for rid, path in stale:
        assert rid not in _catalog.data
        assert rid not in _catalog.paths
        assert path not in _catalog.uids
    return len(stale)


def reindex(site, name, catalog=None):
    catalog = catalog or site.portal_catalog
    if name is None:
        for idxname in catalog._catalog.indexes.keys():
            reindex(site, idxname, catalog)
    catalog.manage_reindexIndex(name)


def main(app, idxname):
    for site in app.objectValues('Plone Site'):
        print '== SITE: %s ==' % site.getId()
        setSite(site)
        if product_installed(site, PKGNAME):
            stale = prune_stale_catalog_entries(site)
            if stale:
                print '\tSuccessfully pruned %s stale catalog records' % stale
            print '\tReindexing %s' % idxname
            reindex(site, idxname)
    txn = transaction.get()
    name = "'%s'" % idxname if idxname else '(ALL INDEXES)'
    txn.note('Update: reindexed %s index for %s' % (
        name,
        site.getId(),
        ))
    txn.commit()


if __name__ == '__main__' and 'app' in locals():
    idxname = sys.argv[-1]
    if idxname.endswith('.py'):
        print 'No index name has been provided, reindexing all indexes.'
        idxname = None
    main(app, idxname)  # noqa

