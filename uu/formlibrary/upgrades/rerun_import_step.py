import sys

import transaction
from zope.component.hooks import setSite

PKGNAME = 'uu.formlibrary'
PROFILE = 'profile-%s:default' % PKGNAME


_installed = lambda site: site.portal_quickinstaller.isProductInstalled
product_installed = lambda site, name: _installed(site)(name)


def install_step(site, stepname):
    gs = site.portal_setup
    if stepname not in gs.getSortedImportSteps():
        raise ValueError('unknown import step named %s' % stepname)
    r = gs.runImportStepFromProfile(PROFILE, 'typeinfo', False)
    print '\n\n== SITE: %s ==\n' % site.getId()
    print r.get('messages').get(stepname)


def main(app, stepname):
    for site in app.objectValues('Plone Site'):
        setSite(site)
        if product_installed(site, PKGNAME):
            
            install_step(site, stepname.strip())
    txn = transaction.get()
    txn.note('Update: run import step %s for profile %s' % (
        stepname,
        PROFILE,
        ))
    txn.commit()


if __name__ == '__main__' and 'app' in locals():
    stepname = sys.argv[-1]
    if stepname.endswith('.py'):
        print 'No step name has been provided'
        exit(0)
    main(app, stepname)  # noqa

