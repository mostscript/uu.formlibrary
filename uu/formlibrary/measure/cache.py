import sys

from interfaces import IDataPointCache
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.utils import getToolByName
from BTrees.OOBTree import OOBTree
from zope.annotation.interfaces import IAnnotations
from zope.component import adapts
from zope.component.hooks import getSite
from zope.interface import implements

from uu.workflows.utils import history_log
from uu.formlibrary import product_log
from uu.formlibrary.interfaces import FORM_TYPES
from uu.formlibrary.measure.interfaces import MEASURE_DEFINITION_TYPE
from uu.formlibrary.measure.interfaces import GROUP_TYPE
from utils import isbrain, modified


ANNO_KEY = 'uu.formlibrary.DATAPOINTCACHE'


# cache key for a datapoint for form (or brain-for-form) context:
def datapoint_cache_key(method, self, context):
    """
    Return four item tuple of UID/modified for each of measure, form
    context.  If measure or form is modified, key is naturally not
    up-to-date, which avoids struggles with invalidation if this key
    is consistently used in all places we might need to cache.

    Note: use string timestamps for cache keys, as they should consume
    half the space (persisted) or RAM as storing a DateTime 3.x object.
    """
    usebrain = isbrain(context)
    # consistent UID getter works with brains and form content:
    _uid = lambda o: o.UID if usebrain else IUUID(o)
    # consistent timestamp getter for content objects and brains:
    return (
        IUUID(self),
        modified(self),
        _uid(context),
        modified(context),
        )


def _get(uid, site=None):
    """
    Unlike implementation of plone.app.uuid.utils.uuidToObject(),
    this function does not do permissions checks to obtain object.
    """
    site = site or getSite()
    catalog = getToolByName(site, 'portal_catalog')
    r = catalog.unrestrictedSearchResults({'UID': uid})
    return r[0]._unrestrictedGetObject() if r else None


class DataPointCache(object):
    """
    Adapts Plone site, fronts for mappings stored in annotations
    to provide for IDataPointCache implementation for the site.
    """
    
    implements(IDataPointCache)
    adapts(ISiteRoot)
    
    content_key = 'uid_keys'
    data_cache_key = 'data_cache'
    
    def __init__(self, context=None):
        self.context = context if context is not None else getSite()
        self._load()

    def _load(self):
        annotations = IAnnotations(self.context)
        data = annotations.get(ANNO_KEY)
        if data is None:
            annotations[ANNO_KEY] = data = PersistentMapping()
        self._content_keys = data.get(self.content_key)
        if self._content_keys is None:
            self._content_keys = data[self.content_key] = OOBTree()
        self._data_cache = data.get(self.data_cache_key)
        if self._data_cache is None:
            self._data_cache = data[self.data_cache_key] = OOBTree()
        self.catalog = getToolByName(self.context, 'portal_catalog')

    def search(self, query):
        return self.catalog.unrestrictedSearchResults(query)

    def _normalize_key(self, key):
        """
        Validates and normalizes key to four item tuple, or raises
        KeyError if key cannot be validated and normalized.
        """
        _key = list(key)
        if len(key) != 4:
            raise KeyError('improper key size, must be four-item sequence.')
        _key = map(lambda v: str(v).strip(), _key)
        isuid = lambda v: len(v.replace('-', '')) == 32
        if not (isuid(key[0]) and isuid(key[2])):
            raise KeyError('improper form and/or measure UIDs in key.')
        return tuple(_key)

    # basic mapping and enumeration/iteration methods:

    def __getitem__(self, key):
        v = self.get(key)
        if v is None:
            raise ValueError
        return v
    
    def get(self, key, default=None):
        key = self._normalize_key(key)
        return self._data_cache.get(key)

    def keys(self):
        return list(self.iterkeys())
    
    def iterkeys(self):
        return self._data_cache.iterkeys()
    
    def items(self):
        return list(self.iteritems())
        
    def iteritems(self):
        return self._data_cache.iteritems()
    
    def values(self):
        return list(self.itervalues())
    
    def itervalues(self):
        return self._data_cache.itervalues()

    def __contains__(self, key):
        key = self._normalize_key(key)
        return key in self._data_cache

    def __len__(self):
        return len(self._data_cache)

    # mapping write methods (basic):
    
    def store(self, key, value):
        key = self._normalize_key(key)
        if not isinstance(value, PersistentMapping):
            value = PersistentMapping(value)
        self._data_cache[key] = value
        ## content-UID to keys, used by self.select(),
        ##  self.reload(), and self.invalidate()
        for uid in (key[0], key[2]):
            if not self._content_keys.get(uid):
                self._content_keys[uid] = PersistentList()
            self._content_keys[uid].append(key)

    __setitem__ = store

    def __delitem__(self, key):
        key = self._normalize_key(key)
        if key not in self._data_cache:
            raise KeyError(key)
        measure_uid, form_uid = key[0], key[2]
        del(self._data_cache[key])
        for uid in (measure_uid, form_uid):
            if uid in self._content_keys:
                if key in self._content_keys[uid]:
                    self._content_keys[uid].remove(key)

    # content-UID to key selection:
    
    def select(self, uid):
        uid = str(uid)
        keys = self._content_keys.get(uid)
        return filter(lambda k: k in self, keys) if keys else []

    def invalidate(self, uid):
        uid = str(uid)
        for key in self.select(uid):
            del(self[key])  # will also invalidate _content_keys
    
    def _content_brain(self, uid):
        r = self.search({'UID': uid})
        if not r:
            return None
        return r[0]
    
    def reload(self, uid):
        uid = str(uid)
        self.invalidate(uid)
        ## now determine if uid is for measure or for a form:
        brain = self._content_brain(uid)
        if brain is None:
            # in cases (e.g. testing) where no brain, just invalidate (above)
            return
        if brain.portal_type == MEASURE_DEFINITION_TYPE:
            self._cache_datapoints_for_measure(uid)
        else:
            self._cache_datapoints_for_form(uid)
    
    def _related_form_uids(self, uid):
        """
        Given measure UID, list related form UIDs such that both the
        form and the measure group containing relevant measures
        use the same form definition.
        """
        measure = _get(uid, self.context)
        group = measure.__parent__
        formdefn_uid = group.definition
        form_query = {
            'references': formdefn_uid,
            'portal_type': FORM_TYPES,
            }
        form_uids = map(lambda b: b.UID, self.search(form_query))
        return form_uids
    
    def _cache_datapoints_for_measure(self, uid):
        """
        Given measure UID, cache form values for all forms using the
        same form definition as measure.
        """
        measure = _get(uid, self.context)
        for f_uid in self._related_form_uids(uid):
            form = _get(f_uid, self.context)
            key = datapoint_cache_key(None, measure, form)
            try:
                point = measure._datapoint(form)
                self.store(key, point)
            except KeyError:
                print 'Could not compute point for %s + %s' % (
                    '/'.join(measure.getPhysicalPath()),
                    '/'.join(form.getPhysicalPath())
                    )

    def _related_measure_uids(self, uid):
        """
        Given a form UID, list related measure UIDs, such that
        both the form and the measure group containing relevant measures
        use the same form definition.
        """
        form = _get(uid, self.context)
        formdefn_uid = form.definition  # use UID, do not resolve directly
        group_query = {
            'references': formdefn_uid,
            'portal_type': GROUP_TYPE,
            }
        group_paths = map(lambda b: b.getPath(), self.search(group_query))
        measure_query = {
            'path': group_paths,
            'portal_type': MEASURE_DEFINITION_TYPE,
            }
        measureuids = map(
            lambda brain: brain.UID,
            self.search(measure_query),
            )
        return measureuids

    def _cache_datapoints_for_form(self, uid):
        """
        Given form UID, cache form values for all applicable measures,
        where applicable is defined as all measures in groups using the
        same form definition as the form.
        """
        form = _get(uid, self.context)
        for m_uid in self._related_measure_uids(uid):
            measure = _get(m_uid, self.context)
            key = datapoint_cache_key(None, measure, form)
            try:
                point = measure._datapoint(form)
                self.store(key, point)
            except KeyError:
                exc = sys.exc_info()
                product_log.warn(
                    'Measure %s unable to cache point for form %s -- %s' % (
                        measure,
                        form,
                        exc[1].message,
                    ))

    def warm(self):
        """Warm cache, site-wide"""
        measure_query = {
            'portal_type': MEASURE_DEFINITION_TYPE,
            }
        measure_brains = self.search(measure_query)
        for brain in measure_brains:
            self.reload(brain.UID)


def handle_simpleform_modify(context, event):
    # invalidate all cached data points to which the form is relevant:
    DataPointCache().reload(IUUID(context))


def handle_measure_modify(context, event):
    # set modification time and a history log message:
    msg = 'Updated modification timestamp, which invalidates stale '\
          'cached queries, datapoints.'
    history_log(context, message=msg, set_modified=True)
    # Invalidate IComposedQuery adapter lookups for measure for
    # both numerator and denominator:
    context._v_q_numerator = None
    context._v_q_denominator = None
    # invalidate cache of built repoze.catalog query:
    context._v_query_numerator = None
    context._v_query_denominator = None
    # ensure that all connections, instances, threads have fresh objects,
    # with no stale _v_ prefixed volatile attributes -- invalidates the
    # measure for all ZODB connections:
    context._p_changed = True
    # invalidate all cached data points to which the measure is relevant:
    DataPointCache().reload(IUUID(context))

