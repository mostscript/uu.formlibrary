import itertools
import json

from zope.globalrequest import getRequest
from zope.interface import implements
from zope.publisher.interfaces.browser import IBrowserPublisher
from zope.publisher.interfaces import NotFound

from interfaces import IComparator, IComparators


_u = lambda v: v if isinstance(v, unicode) else str(v).decode('utf-8')

_is_iter = lambda v: not isinstance(v, basestring) and hasattr(v, '__iter__')


class ComparatorInfo(object):
    implements(IComparator)
    
    def __init__(self, name, label=None, description=None, symbol=None):
        self.name = _u(name)
        self.label = _u(label) if label else self.name
        self.description = _u(description) if description else None
        self.symbol = _u(symbol) if symbol else None
    
    def display_label(self):
        """
        merges symbol with label for a display label appropriate
        in some contexts.
        """
        if not self.symbol:
            return self.label
        return u'%s %s' % (self.symbol, self.label)


ALL = ComparatorInfo(u'All', u'contains all of', symbol=u'\u2286')
ANY = ComparatorInfo(u'Any', u'includes any of', symbol=u'*')
CONTAINS = ComparatorInfo(u'Contains', u'contains', symbol=u'\u2208')
DOESNOTCONTAIN = ComparatorInfo(
    u'DoesNotContain',
    u'does not contain',
    symbol=u'\u2209',
    )
EQ = ComparatorInfo(u'Eq', u'is equal to', symbol=u'=')
GE = ComparatorInfo(u'Ge', u'is greater than or equal to', symbol=u'\u2264')
GT = ComparatorInfo(u'Gt', u'is greater than', symbol=u'>')
INRANGE = ComparatorInfo(u'InRange', u'is between', symbol=u'(\u2026)')
LE = ComparatorInfo(u'Le', u'is less than or equal to', symbol=u'\u2265')
LT = ComparatorInfo(u'Lt', u'is less than', symbol=u'<')
NOTEQ = ComparatorInfo(u'NotEq', u'is not', symbol=u'\u2260')
NOTINRANGE = ComparatorInfo(u'NotInRange', u'is not between', symbol=u'\u2209')

COMPARATORS = (
    ALL,
    ANY,
    CONTAINS,
    DOESNOTCONTAIN,
    EQ,
    GE,
    GT,
    INRANGE,
    LE,
    LT,
    NOTEQ,
    NOTINRANGE,
    )


COMPARATORS_BY_INDEX = {
    'field': (ANY, EQ, GE, GT, INRANGE, LE, LT, NOTEQ, NOTINRANGE),
    'text': (CONTAINS, DOESNOTCONTAIN),
    'keyword': (ANY, ALL, DOESNOTCONTAIN),
    }


class ComparatorRepresentation(object):
    """
    Wrapper for comparator providing JSON representation
    and a __parent__ pointer for object publishing security.
    """
    def __init__(self, context, request, comparator):
        self.__parent__ = self.context = context
        self.comparator = comparator
        self.request = getRequest() if request is None else request
    
    def __call__(self, *args, **kwargs):
        include = ('name', 'label', 'description', 'symbol')
        result = {}
        for name in include:
            v = getattr(self.comparator, name, None)
            if v is not None:
                result[name] = v
        msg = json.dumps(result, indent=2)
        if self.request is not None:
            self.request.response.setHeader('Content-length', str(len(msg)))
            self.request.response.setHeader('Content-type', 'application/json')
        return msg


class Comparators(object):
    
    implements(IComparators, IBrowserPublisher)
    
    def __init__(self, request=None):
        self.request = getRequest() if request is None else request
        self._map = dict((c.name, c) for c in COMPARATORS)
    
    def get(self, name, default=None):
        return self._map.get(_u(name), None)
    
    def __getitem__(self, name):
        v = self.get(name, None)
        if v is None:
            raise KeyError(name)
        return v
    
    def keys(self):
        return self._map.keys()
    
    def iterkeys(self):
        return self._map.keys().__iter__()
    
    def itervalues(self):
        return itertools.imap(lambda k: self.get(k), self.keys())
    
    def iteritems(self):
        return itertools.imap(lambda k: (k, self.get(k)), self.keys())
    
    def values(self):
        return list(self.itervalues())
    
    def items(self):
        return list(self.iteritems())
    
    def __len__(self):
        return len(self._map)
    
    def __contains__(self, name):
        return _u(name) in self._map
    
    def __call__(self, symbols=False, byindex=None, choice=False):
        """
        Return list of (name, label) tuples, optionally filtered
        by index type (1..* names as sequence or delimited string).
        """
        keys = sorted(self.keys())
        _label = lambda name: self.get(name).label
        if symbols:
            _label = lambda name: self.get(name).display_label()
        if byindex is not None:
            if not _is_iter(byindex):
                byindex = str(byindex).split()  # 1..* delimited by spaces
            _keys = set()
            for idxtype in byindex:
                if idxtype in COMPARATORS_BY_INDEX:
                    comparators = COMPARATORS_BY_INDEX[idxtype]
                    _keys = _keys.union(c.name for c in comparators)
            if _keys:
                keys = [k for k in keys if k in _keys]  # orig order was sorted
        if choice:
            ## controlled vocabulary has no range comparison, only membership
            _omit = ('Lt', 'Le', 'Gt', 'Ge', 'InRange', 'NotInRange')
            return [(k, _label(k)) for k in keys if k not in _omit]
        return [(k, _label(k)) for k in keys]

    def publish_json(self, symbols=False, byindex=None, choice=False):
        if self.request is not None:
            form = self.request.form
            if 'symbols' in form:
                symbols = True
            if 'byindex' in form:
                _byindex = str(form.get('byindex'))
                if _byindex and _byindex in COMPARATORS_BY_INDEX:
                    byindex = _byindex
            if 'choice' in form:
                choice = True
        v = self(symbols=symbols, byindex=byindex, choice=choice)
        v = json.dumps(v, indent=2)
        if self.request is not None:
            self.request.response.setHeader('Content-type', 'application/json')
            self.request.response.setHeader('Content-length', str(len(v)))
        return v
    
    ## IBrowserPublisher / IPublishTraverse methods:
    
    def publishTraverse(self, request, name):
        if name == 'publish_json':
            if self.request is not request:
                self.request = request
            return self.publish_json  # callable method
        if name in self._map:
            return ComparatorRepresentation(self, request, self.get(name))
        raise NotFound(self, name, request)
    
    def browserDefault(self, request):
        if request:
            return self, ('publish_json',)
        return self, ()

