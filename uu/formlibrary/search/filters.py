from datetime import date
import itertools
import json
import uuid

from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone.dexterity.content import Item
from plone.uuid.interfaces import IUUID
from repoze.catalog import query
import transaction
from zope.component import adapts, adapter
from zope.dottedname.resolve import resolve
from zope.interface import implements, implementer
from zope.interface.interfaces import IInterface
from zope.location.location import LocationProxy
from zope.proxy import ProxyBase, removeAllProxies, non_overridable
from zope.schema import getFieldNamesInOrder
from zope.schema import interfaces as fieldtypes

from uu.retrieval.utils import identify_interface
from uu.smartdate.converter import normalize_usa_date

from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.search.interfaces import COMPARATORS
from uu.formlibrary.search.interfaces import IFieldQuery
from uu.formlibrary.search.interfaces import IJSONFilterRepresentation
from uu.formlibrary.search.interfaces import IRecordFilter, IFilterGroup
from uu.formlibrary.search.interfaces import IComposedQuery

from uu.formlibrary.measure.interfaces import IMeasureDefinition


# field serialization, used by FieldQuery:
field_id = lambda f: (identify_interface(f.interface), f.__name__)
resolvefield = lambda t: resolve(t[0])[t[1]]  # (name, fieldname) -> schema

# comparator class resolution from identifier:
comparator_cls = lambda v: getattr(query, v) if v in COMPARATORS else None


# proxy used for aq/location breadcrumbs on stored query components' context:

class BaseProxy(LocationProxy):
    """
    A location proxy that is deferrent to the __name__ of the proxied object,
    if it is non-None value.
    """
    
    @property
    def __name__(self):
        if self._name is not None:
            return self._name
        return removeAllProxies(self).__name__
    
    @__name__.setter
    def __name__(self, value):
        self._name = value
    
    def __init__(self, o):
        ProxyBase.__init__(self, o)
        self._name = getattr(o, '__name__', None)


class FilterProxy(BaseProxy):
    """
    Special proxy for IRecordFilter objects, the purpose of this is
    to work around limitations of zope.proxy when the class of a
    proxied object binds 'self' to the unwrapped object.  Here, we
    need to have schema() -- and validate(), add() methods, which call
    it -- bind the wrapped proxy as self before calling, which is
    unfortunately necessary to make the __parent__ acquisition work
    from the filter all the way to the containing measure definition.
    """

    @non_overridable
    def schema(self):
        return CoreFilter.schema(self)

    @non_overridable
    def validate(self, *args, **kwargs):
        return CoreFilter.validate(self, *args, **kwargs)

    @non_overridable
    def add(self, *args, **kwargs):
        return CoreFilter.add(self, *args, **kwargs)


class SequenceIterator(object):
    """
    An iterator for a sequence that uses __getitem__ to fetch elements of
    the sequence.
    """
    
    def __init__(self, context):
        self.context = context
        self._cursor = 0

    def next(self):
        try:
            v = self.context[self._cursor]
            self._cursor += 1
        except IndexError:
            raise StopIteration()
        return v

    def __iter__(self):
        return self


class SequenceLocationProxy(BaseProxy):
    """
    A location proxy that behaves much like implicit acquisition for
    nested persistent lists.  This means that traversal over listed
    persistent or listed elements should yield a way to walk back up
    parent objects to the root proxy (which may yet have its __parent__)
    set too (this supports walking with Acquisition.aq_parent() too).
    """
    
    def __getitem__(self, i, proxy=None):
        v = super(SequenceLocationProxy, self).__getitem__(i)
        if IRecordFilter.providedBy(v):
            proxy = FilterProxy(v)
        elif isinstance(v, PersistentList):
            proxy = SequenceLocationProxy(v)
        elif isinstance(v, Persistent):
            proxy = BaseProxy(v)
        if proxy is not None:
            proxy.__parent__ = self
            return proxy
        return v

    def __iter__(self):
        return SequenceIterator(self)


# get index type from FieldQuery
def query_idxtype(q):
    """Get index type for specific comparator, field combination"""
    comparator, field = q.comparator, q.field

    # for text, whether to use text index or field index depends on the
    # comparator saved on the query:
    line_types = (fieldtypes.ITextLine, fieldtypes.IBytesLine)
    if any([iface.providedBy(field) for iface in line_types]):
        if comparator in ('Contains', 'DoesNotContain'):
            return 'keyword'
        return 'field'
    # special-case overlapping comparators used in multiple field types
    if fieldtypes.ISequence.providedBy(field) and comparator == 'Any':
        return 'keyword'
    # for all other field types, use 1:1 mapping:
    idxtypes = {
        # comparator name key: index type label value
        'Any': 'field',
        'All': 'keyword',
        'DoesNotContain': 'keyword',
        'Eq': 'field',
        'Ge': 'field',
        'Gt': 'field',
        'InRange': 'field',
        'Le': 'field',
        'Lt': 'field',
        'NotEq': 'field',
        'NotInRange': 'field',
    }
    if comparator in idxtypes:
        return idxtypes.get(comparator)
    return 'field'  # fallback default


def query_object(q):
    """
    Get a repoze.catalog query object for a field query, using
    contentions for index naming from uu.retrieval.
    """
    idxtype = query_idxtype(q)
    idxname = '%s_%s' % (idxtype, q.field.__name__)
    return comparator_cls(q.comparator)(idxname, q.value)


def filter_query(f):
    """
    Given a record filter, get repoze.catalog query object
    representative of filter and contained field queries.
    """
    if len(f) == 1:
        # no BoolOp for single field, just comparator query:
        return query_object(f.values()[0])
    op = query.Or
    opname = f.operator
    if opname == 'AND':
        op = query.And
    queries = [query_object(q) for q in f.values()]
    return op(*queries)


def diffquery(*queries):
    """
    Factory for relative complement of results for queries A \ B \ ...
    Or A minus anything matching any of the subsequent queries.
    """
    if len(queries) == 0:
        raise ValueError('empty query arguments')
    if len(queries) == 1:
        return queries[0]
    return query.And(queries[0], query.Not(query.Or(*queries[1:])))


def setop_query(operator):
    """Return query class or factory callable for operator name"""
    return {
        'union': query.Or,
        'intersection': query.And,
        'difference': diffquery,
        }[operator]


def grouped_query(group):
    """
    Given group as either an IFilterGroup or IComposedQuery
    callable object that returns a query, compose using the set
    operator for that object.
    """
    if len(group) == 1:
        # avoid unneccessary wrapping when only one item in group
        if IComposedQuery.providedBy(group):
            return grouped_query(group[0])
        else:
            return filter_query(group[0])
    return setop_query(group.operator)(*[item.build() for item in group])


class FieldQuery(Persistent):
    """
    FieldQuery is field / value / comparator entry.  Field is persisted
    using serialization (tuple of dotted name of interface, fieldname),
    but resolution of field object is cached indefinitely in volatile.
    """
    implements(IFieldQuery)

    def __init__(self, field, comparator, value):
        if not fieldtypes.IField.providedBy(field):
            raise ValueError('field provided must be schema field')
        self._field_id = field_id(field)
        self.comparator = str(comparator)
        self.value = value

    def build(self):
        return query_object(self)

    def _get_field(self):
        if not getattr(self, '_v_field', None):
            self._v_field = resolvefield(self._field_id)
        return self._v_field

    def _set_field(self, field):
        self._field_id = field_id(field)
        self._v_field = field

    field = property(_get_field, _set_field)

    def _set_value(self, value):
        self._get_field().validate(value)
        self._value = value

    def _get_value(self):
        return self._value

    value = property(_get_value, _set_value)

    def validate(self, iface):
        return (self._get_field().interface is iface)


@implementer(IFormDefinition)
@adapter(IRecordFilter)
def filter_definition(context):
    # get composed query, which contains, group, then filter context:
    composed_query = context.__parent__.__parent__
    measure_definition = composed_query.__parent__
    return IFormDefinition(measure_definition)


class CoreFilter(Persistent):
    """Core persistent record filter implementation"""

    implements(IRecordFilter)

    __parent__ = None

    def __init__(self, *args, **kwargs):
        super(CoreFilter, self).__init__(*args, **kwargs)
        self._uid = str(uuid.uuid4())
        self.reset(**kwargs)

    @property
    def __name__(self):
        return self._uid

    def reset(self, **kwargs):
        self.operator = kwargs.get('operator', 'AND')
        self._queries = PersistentMapping()
        self._order = PersistentList()

    def schema(self):
        """
        Assume definition bound to RecordFilter always provides schema
        at attribute name of 'schema'.
        """
        definition = IFormDefinition(self)
        return definition.schema

    def validate(self):
        schema = self.schema()
        for query in self._queries.values():
            query.validate(schema)

    def build(self):
        return filter_query(self)

    def add(self, query=None, **kwargs):
        if query is None:
            ## attempt to make query from kwargs given either
            ## field/comparator/value or fieldname/comparator/value
            field = kwargs.get('field', None)
            fieldname = kwargs.get('fieldname', None)
            if not (field or fieldname):
                raise ValueError('Field missing for query construction')
            if field is None and fieldname:
                field = self.schema()[fieldname]
            comparator = kwargs.get('comparator', None)
            value = kwargs.get('value', None)
            if not (value and comparator):
                raise ValueError('Missing value or comparator')
            query = FieldQuery(field, comparator, value)
        query.validate(self.schema())
        fieldname = query.field.__name__
        self._queries[fieldname] = query
        self._order.append(fieldname)

    def remove(self, query):
        if IFieldQuery.providedBy(query):
            query = query.field.__name__
        if query not in self._queries:
            raise KeyError('Query not found (fieldname: %s)' % query)
        del(self._queries[query])
        self._order.remove(query)

    ## RO mapping interface
    def get(self, name, default=None):
        return self._queries.get(name, default)

    def __len__(self):
        return len(self._order)

    def __getitem__(self, name):
        v = self.get(name, None)
        if v is None:
            raise KeyError(name)  # fieldname not found
        return v

    def __contains__(self, name):
        if IFieldQuery.providedBy(name):
            name = name.field.__name__
        return name in self._order

    def keys(self):
        return list(self._order)

    def iterkeys(self):
        return self._order.__iter__()

    def itervalues(self):
        return itertools.imap(lambda k: self.get(k), self.iterkeys())

    def iteritems(self):
        return itertools.imap(lambda k: (k, self.get(k)), self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())


class RecordFilter(CoreFilter, Item):
    """
    Contentish record filter BBB.

    MRO note: CoreFilter defined as first superclass to avoid collection
    methods such as OFS.__len__() via Item.
    """

    def __init__(self, id=None, *args, **kwargs):
        Item.__init__(self, id, *args, **kwargs)
        CoreFilter.__init__(self, *args, **kwargs)
        self.reset(**kwargs)

    @property
    def externalEditorEnabled(self):
        return False


class FilterJSONAdapter(object):
    """
    Multi-adapts a filter and a schema to serialize the filter in
    that schema's context to appropriate JSON, and to marshal JSON
    back into a filter containing field queries.  Also supports
    constructing and consuming equivalent python dict to JSON.

          ________________
         |      DATA      |
         |----------------+
         | operator : str | 1  * ___________________
         | rows : list    |<>---|   Row             |
          ----------------      +-------------------+
                                | fieldname : str   |
                                | comparator : str  |
                                | value             |
                                 -------------------
    """
    implements(IJSONFilterRepresentation)
    adapts(IRecordFilter, IInterface)

    def __init__(self, context, schema):
        if not IRecordFilter.providedBy(context):
            raise ValueError('context must provide IRecordFilter')
        if not IInterface.providedBy(schema):
            raise ValueError('schema provided must be interface')
        self.context = context
        self.schema = schema

    def normalize_value(self, field, value):
        if fieldtypes.IBool.providedBy(field):
            return True if value.lower() == 'yes' else False
        if fieldtypes.IDate.providedBy(field):
            if isinstance(value, basestring):
                usa_date = normalize_usa_date(value)
                if usa_date is not None:
                    return usa_date  # M/D/YYYY -> date
                return date(*(map(lambda v: int(v), value.split('-'))))  # ISO
        if fieldtypes.IInt.providedBy(field):
            return int(value)
        if fieldtypes.IFloat.providedBy(field):
            return float(value)
        return value

    def update(self, data):
        """
        Update from JSON data or equivalent dict.
        """
        if isinstance(data, basestring):
            data = json.loads(data)
        queries = []
        fieldnames = getFieldNamesInOrder(self.schema)
        for query_row in data.get('rows', []):
            fieldname = query_row.get('fieldname')
            if fieldname not in fieldnames:
                continue  # ignore possibly removed fields
            field = self.schema[fieldname]
            comparator = query_row.get('comparator')
            value = self.normalize_value(
                field,
                query_row.get('value'),
                )
            queries.append(FieldQuery(field, comparator, value))
        self.context.reset()  # clear queries
        self.context.operator = data.get('operator', 'AND')
        r = map(self.context.add, queries)  # add all  # noqa

    def _serialize_value(self, field, value):
        if value and fieldtypes.IDate.providedBy(field):
            return value.strftime('%Y-%m-%d')
        return value

    def _mkrow(self, query):
        row = {}
        row['fieldname'] = query.field.__name__
        row['value'] = self._serialize_value(query.field, query.value)
        row['comparator'] = query.comparator
        return row

    def serialize(self, use_json=True):
        """
        Serialze queries of context to JSON, or if use_json is False, to an
        equivalent dict of data.
        """
        data = {}
        data['operator'] = self.context.operator
        data['rows'] = [self._mkrow(q) for q in self.context.values()]
        if use_json:
            return json.dumps(data, indent=4)
        return data


class BaseGroup(PersistentList):

    __parent__ = None

    def __init__(self, operator='union', items=()):
        self.operator = operator
        # UUID is relevant to FilterGroup, safe to ignore on ComposedQuery
        self._uid = str(uuid.uuid4())
        super(BaseGroup, self).__init__(items)

    @property
    def __name__(self):
        return self._uid

    def move(self, item, direction='top'):
        """
        Move item (uid or filter) to direction specified,
        up/down/top/bottom
        """
        if direction not in ('top', 'bottom', 'up', 'down'):
            raise ValueError('invalid direction')
        if isinstance(item, basestring):
            found = [f for f in self if f._uid == item]
            if not found:
                raise ValueError('item %s not found' % item)
            item = found[0]
        idx = self.index(item)
        d_idx = {
            'up': 0 if idx == 0 else (idx - 1),
            'down': idx + 1,
            'top': 0,
            'bottom': len(self),
            }[direction]
        self.insert(d_idx, self.pop(idx))

    def build(self):
        """construct a repoze.catalog query"""
        return grouped_query(self)


class FilterGroup(BaseGroup):

    implements(IFilterGroup)


class ComposedQuery(BaseGroup):
    
    implements(IComposedQuery)

    def __init__(self, name, operator='union', items=()):
        super(ComposedQuery, self).__init__(operator, items)
        self.name = str(name)


# UUID adapters for IRecordFilter, IFilterGroup:

def _getuid(context):
    return getattr(context, '_uid', None)


@implementer(IUUID)
@adapter(IRecordFilter)
def filter_uid(context):
    return _getuid(context)


@implementer(IUUID)
@adapter(IFilterGroup)
def group_uid(context):
    return _getuid(context)


def empty_query(name):
    """Scaffolding"""
    f = CoreFilter()
    g = FilterGroup(items=(f,))
    f.__parent__ = g
    q = ComposedQuery(name, items=(g,))
    g.__parent__ = q
    return q


def composed_storage():
    storage = PersistentMapping()
    storage['numerator'] = empty_query('numerator')
    storage['denominator'] = empty_query('denominator')
    return storage


def _measure_composed_query(context, name):
    _attr = '_composed_queries'
    if name not in ('numerator', 'denominator'):
        raise ValueError('invalid composed query name')
    if not hasattr(context, _attr):
        setattr(context, _attr, composed_storage())
        transaction.get().note('Added composed query storage to measure')
    composed = SequenceLocationProxy(getattr(context, _attr).get(name))
    composed.__parent__ = context
    return composed

    
@implementer(IComposedQuery)
@adapter(IMeasureDefinition)
def measure_numerator(context):
    if not getattr(context, '_v_q_numerator', None):
        context._v_q_numerator = _measure_composed_query(context, 'numerator')
    return context._v_q_numerator


@implementer(IComposedQuery)
@adapter(IMeasureDefinition)
def measure_denominator(context):
    if not getattr(context, '_v_q_denominator', None):
        context._v_q_denominator = _measure_composed_query(
            context,
            'denominator',
            )
    return context._v_q_denominator

