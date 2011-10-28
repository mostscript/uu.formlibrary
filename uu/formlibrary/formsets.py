import itertools

from plone.dexterity.content import Item
from zope.component import adapts
from zope.interface import implements
from zope.app.component.hooks import getSite
from Products.CMFCore.utils import getToolByName

from uu.formlibrary.interfaces import IFormQuery, IFormSet, IFormDefinition
from uu.formlibrary.interfaces import FORM_TYPES


class FormSetSpecifier(Item):
    implements(IFormQuery)

    def _query(self):
        idxmap = {
            'query_title' : 'Title',
            'query_subject' : 'Subject',
            'query_state' : 'review_state',
            'query_start' : 'start',
            'query_end' : 'end',
            }
        q = {'portal_type': FORM_TYPES}
        for name in idxmap:
            idx = idxmap[name]
            v = getattr(self, name, None)
            if v:
                # only non-empty values are considered
                q[name] = v
        return q
    
    def __iter__(self): 
        """
        Return iterator of (key,value) tuples such that
        an instance of this class can be cast to a dict.
        """
        return self._query.items().__iter__()


# form set adapters:

class BaseFormSet(object):
    """
    Adapter shared implementation, assumes UUID keys are 
    generated from the set self.contents, which is populated 
    by the constructors of subclasses of this.
    """
   
    def __init__(self, context, name=None):
        self.name = name
        if getattr(self, 'contents', None) is None:
            self.contents = set()
        self.site = getSite()
        self.catalog = getToolByName(self.site, 'portal_catalog')
        self.context = context

    def get(self, key, default=None):
        if key not in self.keys():
            return default
        r = self.catalog.search({'UID': str(key)})
        if not r:
            return default
        return r[0]._unrestrictedGetObject()
    
    def __getitem__(self, key):
        v = self.get(key)
        if v is None:
            msg = 'key not found %s' % key
            if key in self.keys():
                msg += ' (value for key unlocatable)'
            raise KeyError(msg)
        return v
    
    def __contains__(self, key):
        return key in self.contents
    
    def keys(self):
        return list(self.contents) # set->list
    
    def __len__(self):
        return len(self.contents)
    
    def iterkeys(self):
        return self.keys().__iter__()
   
    __iter__ = iterkeys

    def itervalues(self):
        return itertools.imap(self.__getitem__, self.keys())
    
    def iteritems(self):
        itemtuple = lambda k: (k, self[k])
        return itertools.imap(itemtuple, self.keys())
    
    def values(self):
        return list(self.itervalues())
   
    def items(self):
        return list(self.iteritems())
    
    def _key_repr(self, suffix=''):
        k = self.keys()
        if len(k) > 10:
            k = k[:10]
            suffix = ', ...'
        return ', '.join(["'%s'" % uid for uid in k]) + suffix

    def __repr__(self):
        return '<%s [%s] at %s>' % (
            self.__class__.__name__,
            self._key_repr(),
            hex(id(self)),
            )
    
    def _normalized_other(self, other):
        """if other is a python set/frozenset, wrap it"""
        rv = other
        if isinstance(other, frozenset) or isinstance(other, set):
            rv = self.copy()
            rv.contents = set(other)
        return rv
   
    def _set_op(self, other, fname):
        """generalized proxy to compare sets self.contents, other"""
        other = self._normalized_other(other)
        return getattr(self.contents, fname)(other.contents)

    def isdisjoint(self, other):
        return _set_op(other, 'isdisjoint')

    def __and__(self, other):
        return _set_op(other, '__and__')

    def __or__(self, other):
        return _set_op(other, '__or__')
    
    def __xor__(self, other):
        return _set_op(other, '__xor__')
    
    def __sub__(self, other):
        return _set_op(other, '__sub__')
    
    def __eq__(self, other):
        return _set_op(other, '__eq__')
    
    def __ne__(self, other):
        return _set_op(other, '__ne__')
    
    def __gt__(self, other):
        return _set_op(other, '__gt__')
    
    def __ge__(self, other):
        return _set_op(other, '__ge__')
    
    def __lt__(self, other):
        return _set_op(other, '__lt__')
    
    def __le__(self, other):
        return _set_op(other, '__le__')
    
    issuperset = __ge__
    issubset = __le__
    symetric_difference = __xor__
    union = __or__
    intersection = __and__
    difference = __sub__
    
    def copy(self):
        """
        Create a new definition object (without calling constructor) and copy
        state / attributes to new copy.  Returns object copy.
        """
        o = object.__new__(self.__class__)
        o.contents = self.contents
        o.name = self.name
        o.context = self.context
        o.site = self.site
        o.catalog = self.catalog
        if hasattr(self, 'definition'):
            o.definition = self.definition
        return o


class DefinitionFormSet(BaseFormSet):
    """
    Adapts form definition to a form set describing all forms
    bound to the definition.  This is the event-space for all 
    other possible form sets related to a definition.
    """

    implements(IFormSet)
    adapts(IFormDefinition)
    
    def __init__(self, context):
        if not IFormDefinition.providedBy(context):
            raise ValueError(   
                'context %s does not provide IFormDefinition' % context)
        BaseFormSet.__init__(self, context, name=u'definition')


class QueryFormSet(BaseFormSet):
    """Adapts Form set specifier / IFormQuery into form set"""
    
    implements(IFormSet)
    adapts(IFormQuery)
    
    def __init__(self, context):
        if not IFormQuery.providedBy(context):
            raise ValueError('context %s must provide IFormQuery' % context)
        BaseFormSet.__init__(self, context)
        self.definition = context.__parent__
    
    def _filter_keys(self, keys):
        """
        filter keys to only those inside the event_space of definition
        keys -- use set intersection to guarantee the set of returned
        keys is a subset of all definition keys.
        """
        event_space = DefinitionFormSet(self.definition).contents
        return list(set(keys) & event_space) #filtered to intersection

    def keys(self):
        result = []
        if self.context.target_uids:
            result += self.context.target_uids or []
        query = dict(self.context)
        if not query:
            return self._filter_keys(result) #no query, return selected
        r = self.catalog.search(query)
        if not r:
            return self._filter_keys(result) #just selected, query was empty
        combined = result + [b.UID for b in r] #UIDs selected + UIDs queried
        return self._filter_keys(combined)

