import transaction
from zope.component.hooks import setSite
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent


FORMTYPE = 'uu.formlibrary.multiform'
SITENAMES = ('qiteamspace', 'opip', 'cnhnqi')

def migrate_multiform_add_catalogs(app):
    for name in SITENAMES:
        site = app[name]
        setSite(site)
    r = site.portal_catalog.search({'portal_type': FORMTYPE})
    forms = map(lambda b: b._unrestrictedGetObject(), r)
    for form in forms:
        notify(ObjectModifiedEvent(form))  # forces catalog creation, index
        assert form.catalog is not None
    txn = transaction.get()
    txn.note('/'.join(site.getPhysicalPath()))
    txn.note('Added form search catalogs to all multi-record form instances.')
    txn.commit()


if __name__ == '__main__' and 'app' in locals():
    migrate_multiform_add_catalogs(app)

