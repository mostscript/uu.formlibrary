from AccessControl.SecurityManagement import newSecurityManager
from Acquisition import aq_base
import transaction
from ZPublisher.BaseRequest import RequestContainer
from zope.component.hooks import setSite

from uu.formlibrary.measure.cache import DataPointCache
from uu.formlibrary.tests import test_request

BASE_HOST = 'teamspace1.upiq.org'
VHOSTBASE = '/VirtualHostBase/https/teamspace1.upiq.org'


SITES = {
    'qiteamspace': 'https://projects.upiq.org',
    'cnhnqi': 'https://cnhnqi.childrensnational.org',
    'opip': 'https://projects.oregon-pip.org',
    'maine': 'https://teamspace.mainequalitycounts.org',
    }


def wrap_app_in_request(app):
    """
    Wrap an app in request suitable for execution of templates, and such
    that Traversable.absolute_url() works in a controlled way. Sets
    request['SERVER_URL'] and returns tuple of correctly wrapped app and
    corresponding request object.
    """
    request = test_request()
    request.setServerURL(protocol='http', hostname=BASE_HOST)
    app = app.__of__(RequestContainer(REQUEST=request))
    app.REQUEST = request
    return app, request


def use_admin_user(app):
    user = app.acl_users.getUser('admin')
    newSecurityManager(None, user)


def reload_dp_cache(site):
    cache = DataPointCache(site)
    cache.warm()

def clear_request(app):
    base = aq_base(app)
    if hasattr(base, 'REQUEST'):
        delattr(base, 'REQUEST')


def commit(context, msg):
    txn = transaction.get()
    # Undo path, if you want to use it, unfortunately is site-specific,
    # so use the hostname and VirtualHostMonster path used to access the
    # Application root containing all Plone sites:
    path = '/'.join(context.getPhysicalPath())
    if VHOSTBASE:
        txn.note('%s%s' % (VHOSTBASE, path))
    msg = '%s -- for %s' % (msg or 'Scripted action', path)
    txn.note(msg)
    txn.commit()  # TODO: uncomment after testing, development


def main(app):
    use_admin_user(app)
    for name in SITES.keys():
        app, request = wrap_app_in_request(app)  # clear later, before commit!
        print '== SITE: %s ==' % name
        site = app[name]
        setSite(site)
        # set URL base info for each site:
        base = SITES.get(name)
        request.setServerURL(*base.split('://'))  # (protocol, hostname)
        request.other['VirtualRootPhysicalPath'] = tuple(site.getPhysicalPath())
        reload_dp_cache(site)
        print '\t done.'
        clear_request(app)  # clear the request, ref to it is problem.
        commit(site, 'Reloaded data point cache/index')
        print '\t committed.'


if __name__ == '__main__' and 'app' in locals():
    main(app)  # noqa

