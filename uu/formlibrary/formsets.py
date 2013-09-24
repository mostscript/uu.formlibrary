import itertools

from plone.uuid.interfaces import IUUID
from zope.component import adapts
from zope.interface import implements
from zope.component.hooks import getSite
from Products.CMFCore.utils import getToolByName

from uu.formlibrary.interfaces import IFormSet, IFormDefinition
from uu.formlibrary.interfaces import MULTI_FORM_TYPE, SIMPLE_FORM_TYPE


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
        return list(self.contents)  # set->list

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
        return self._set_op(other, 'isdisjoint')

    def __and__(self, other):
        return self._set_op(other, '__and__')

    def __or__(self, other):
        return self._set_op(other, '__or__')

    def __xor__(self, other):
        return self._set_op(other, '__xor__')

    def __sub__(self, other):
        return self._set_op(other, '__sub__')

    def __eq__(self, other):
        return self._set_op(other, '__eq__')

    def __ne__(self, other):
        return self._set_op(other, '__ne__')

    def __gt__(self, other):
        return self._set_op(other, '__gt__')

    def __ge__(self, other):
        return self._set_op(other, '__ge__')

    def __lt__(self, other):
        return self._set_op(other, '__lt__')

    def __le__(self, other):
        return self._set_op(other, '__le__')

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
        r = self.catalog.search({
            'definition': IUUID(self.context),
            'portal_type': {
                'query': (MULTI_FORM_TYPE, SIMPLE_FORM_TYPE),
                'operator': 'or',
                },
            })
        self.contents = set([b.UID for b in r])


