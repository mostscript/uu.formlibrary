"""
schema_update.py -- update schemas when plone.supermodel serialization
                    changes may affect signatures (usually after Plone
                    upgrades).

USE this as a runscript via ./bin/instance run ...
"""

from AccessControl.SecurityManagement import newSecurityManager
import transaction
from zope.component.hooks import setSite

from uu.formlibrary.handlers import definition_schema_handler
from uu.formlibrary.interfaces import DEFINITION_TYPE
from uu.formlibrary.utils import local_query

SITES = ('qiteamspace', 'cnhnqi', 'opip', 'maine')
VHOSTBASE = '/VirtualHostBase/https/teamspace1.upiq.org'


def migrate_definition_schema(definition):
    definition_schema_handler(definition)  # will load, then reserialize


def migrate_schemas(site):
    q = local_query(site, {}, types=(DEFINITION_TYPE,))
    definitions = site.portal_catalog.unrestrictedSearchResults(q)
    for definition in definitions:
        migrate_definition_schema(definition)


def main(app):
    user = app.acl_users.getUser('admin')
    newSecurityManager(None, user)
    for name in SITES:
        site = app[name]
        setSite(site)
        migrate_schemas(site)
        txn = transaction.get()
        txn.note('%s%s' % (VHOSTBASE, '/'.join(site.getPhysicalPath())))
        txn.note('Migrated schemas to plone.supermodel 1.2.6 syntax')
        txn.commit()

if __name__ == '__main__':
    main(app)   # noqa

