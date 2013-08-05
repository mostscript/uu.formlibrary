import itertools
import json
from datetime import date, datetime

from AccessControl import getSecurityManager
from AccessControl import Unauthorized
import Missing
from plone.app.layout.navigation.root import getNavigationRootObject
from plone.app.uuid.utils import uuidToObject
from Products.CMFCore.permissions import ListFolderContents
from Products.ZCatalog.Lazy import Lazy, LazyCat, LazyMap
from zope.component.hooks import getSite


EMPTY_SET = '[]'  # empty JSON array


def iteminfo(brain):
    path = brain.getPath()
    return {
        'uid': brain.UID or None,
        'path': path,
        'id': path.split('/')[-1],
        'url': brain.getURL(),
        'title': brain.Title.decode('utf-8'),
        'description': brain.Description.decode('utf-8'),
        'portal_type': brain.portal_type,
        'type_name': brain.Type,
        'review_state': brain.review_state,
        'created': brain.created.asdatetime() if brain.created else None,
        'modified': brain.modified.asdatetime() if brain.modified else None,
        'is_folderish': bool(brain.is_folderish),
        }


def lazymap_to_iterator(result):
    if isinstance(result, LazyCat):
        return list(result)  # likely an empty result
    rids = getattr(result, '_seq', result._data.keys())
    fn = result._func
    return itertools.imap(fn, rids)


def remap_result(result):
    """
    Remap brain elements in lazy sequence to a new lazy-evaluated
    sequence containing item info dicts.
    """
    if isinstance(result, LazyCat):
        return result  # likely an empty result
    _getter = result._func
    _info = lambda rid: iteminfo(_getter(rid))
    rids = getattr(result, '_seq', result._data.keys())
    return LazyMap(_info, rids)


def listitems(context,
              portal_type=None,
              recursive=False,
              root=False,
              **kw):
    """
    List items visible to user, as filtered by catalog searchResults(),
    either directly within a path, or recursively in all subfolders; if
    root is specified as a non-False value, then use the navigation root
    as the search path.  Can be filtered on portal_type and on other
    search parameters as keyword arguments.
    """
    site = getSite()
    if root:
        context = getNavigationRootObject(context, site)
    query = {
        'path': {
            'query': '/'.join(context.getPhysicalPath()),
            }
        }
    if not recursive:
        query['path']['depth'] = 1
    if portal_type is not None:
        query['portal_type'] = portal_type
    result = site.portal_catalog.searchResults(
        query,
        **kw
        )
    return {
        'length': len(result),
        'items': remap_result(result),
        }


class JSONListing(object):
    """
    Base JSON listing, lists items immediately in contents of folder
    that are marked as visible to the current user/security context.
    """
    
    RECURSIVE = False
    
    PERMISSION = ListFolderContents
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.message = EMPTY_SET

    def _result(self, container, **kwargs):
        return listitems(
            container,
            recursive=self.RECURSIVE,
            root=kwargs.get('root', False),
            portal_type=kwargs.get('portal_type', None),
            sort_on=kwargs.get('sort_on', 'sortable_title'),
            sort_order=kwargs.get('sort_order', 'ascending'),
            )

    def serializer(self, value):
        """default serializer used by json.dumps()"""
        if isinstance(value, datetime) or isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Lazy):
            return list(value)  # enumerate entire lazy sequence
        if value is Missing.Value:
            return None
        raise TypeError(type(value))

    def update(self, *args, **kwargs):
        self.sm = getSecurityManager()
        container = self.context
        uid = kwargs.get('uid', self.request.get('uid', None))
        if uid is not None:
            container = uuidToObject(uid)
        if not self.sm.checkPermission(self.PERMISSION, container):
            raise Unauthorized('Permission denied')
        self.message = json.dumps(
            self._result(container, **self.request),
            default=self.serializer,
            )
    
    def index(self, *args, **kwargs):
        setHeader = self.request.response.setHeader
        setHeader('Content-type', 'application/json')
        setHeader('Content-length', len(self.message))
        return self.message
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)


class JSONFinder(JSONListing):
    """Recursive JSON listing, finds content in subfolders"""
    
    RECURSIVE = True


