import itertools
import json

from zope.globalrequest import getRequest
from zope.interface import implements
from zope.publisher.interfaces.browser import IBrowserPublisher
from zope.publisher.interfaces import NotFound

from interfaces import IComparator, IComparators


_u = lambda v: v if isinstance(v, unicode) else str(v).decode('utf-8')


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
EQ = ComparatorInfo(u'Eq', u'is equal to', symbol=u'=')
GE = ComparatorInfo(u'Ge', u'is greater than or equal to', symbol=u'\u2264')
GT = ComparatorInfo(u'Gt', u'is greater than', symbol=u'>')
IN = ComparatorInfo(u'In', u'contains', symbol=u'\u2208')
INRANGE = ComparatorInfo(u'InRange', u'is between', symbol=u'(\u2026)')
LE = ComparatorInfo(u'Le', u'is less than or equal to', symbol=u'\u2265')
LT = ComparatorInfo(u'Ge', u'is less than', symbol=u'<')
NOTEQ = ComparatorInfo(u'NotEq', u'is not', symbol=u'\u2260')
NOTIN = ComparatorInfo(u'NotIn', u'does not contain', symbol=u'\u2209')
NOTINRANGE = ComparatorInfo(u'NotInRange', u'is not between', symbol=u'\u2209')

COMPARATORS = (
    ALL,
    ANY,
    EQ,
    GE,
    GT,
    IN,
    INRANGE,
    LE,
    LT,
    NOTIN,
    NOTEQ,
    NOTINRANGE,
    )


FIELD_COMPARATORS = (ANY, EQ, GE, GT, INRANGE, LE, LT, NOTEQ, NOTINRANGE)

TEXT_COMPARATORS = (IN, NOTIN)

KEYWORD_COMPARATORS = (ANY, ALL, NOTIN)


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
    
    def __call__(self, symbols=False):
        """Return list of (name, label) tuples"""
        keys = sorted(self.keys())
        _label = lambda name: self.get(name).label
        if symbols:
            _label = lambda name: self.get(name).display_label()
        return [(k, _label(k)) for k in keys]

    def publish_json(self, symbols=False):
        if self.request is not None:
            if 'symbols' in self.request.form:
                symbols = True
        v = json.dumps(self(symbols=symbols), indent=2)
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

