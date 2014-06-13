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
from zope.schema import getFieldNamesInOrder, ValidationError
from zope.schema import interfaces as fieldtypes

from uu.retrieval.utils import identify_interface
from uu.smartdate.converter import normalize_usa_date

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


# get index type from FieldQuery
def query_idxtype(fieldquery, schema):
    """Get index type for specific comparator, field combination"""
    comparator, fieldname = fieldquery.comparator, fieldquery.fieldname
    field = schema[fieldname]

    # for text, whether to use text index or field index depends on the
    # comparator saved on the query:
    line_types = (fieldtypes.ITextLine, fieldtypes.IBytesLine)
    if any([iface.providedBy(field) for iface in line_types]):
        if comparator in ('Contains', 'DoesNotContain'):
            return 'keyword'
        return 'field'
    # special-case overlapping comparators used in multiple field types
    if fieldtypes.ICollection.providedBy(field) and comparator == 'Any':
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


def query_object(fieldquery, schema):
    """
    Get a repoze.catalog query object for a field query and schema,
    using conventions for index naming from uu.retrieval.
    """
    idxtype = query_idxtype(fieldquery, schema)
    idxname = '%s_%s' % (idxtype, fieldquery.fieldname)
    return comparator_cls(fieldquery.comparator)(idxname, fieldquery.value)


def filter_query(f, schema):
    """
    Given a record filter and a schema, get repoze.catalog query object
    representative of filter and contained field queries.
    """
    if len(f) == 1:
        # no BoolOp for single field, just comparator query:
        return query_object(f.values()[0], schema)
    op = query.Or
    opname = f.operator
    if opname == 'AND':
        op = query.And
    queries = [query_object(q, schema) for q in f.values()]
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


def grouped_query(group, schema):
    """
    Given group as either an IFilterGroup or IComposedQuery, and a
    schema context to apply to, compose a repoze.catalog query using the
    set operator for the group/query object.
    """
    if len(group) == 1:
        # avoid unneccessary wrapping when only one item in group
        if IComposedQuery.providedBy(group):
            return grouped_query(group[0], schema)
        else:
            return filter_query(group[0], schema)
    return setop_query(group.operator)(*[item.build(schema) for item in group])


class FieldQuery(Persistent):
    """
    FieldQuery is field / value / comparator entry.  Field is persisted
    using serialization (tuple of dotted name of interface, fieldname),
    but resolution of field object is cached indefinitely in volatile.
    """
    implements(IFieldQuery)

    _field_id = None   # BBB two-item tuple of schema dottedname, fieldname
    _fieldname = None

    def __init__(self, field, comparator, value):
        if fieldtypes.IField.providedBy(field):
            field = field.__name__    # store fieldname, not field
        self._fieldname = str(field)  # fieldname
        self.comparator = str(comparator)
        self._value = value

    def _get_fieldname(self):
        return self._fieldname or self._field_id[1]  # _field_id for BBB

    def _set_fieldname(self, name):
        self._fieldname = name

    fieldname = property(_get_fieldname, _set_fieldname)

    def field(self, schema):
        name = self.fieldname
        if name in getFieldNamesInOrder(schema):
            return schema[name]
        return None

    def build(self, schema):
        # Validate that the fieldname is known the the schema and the
        # saved query value validates properly before building the
        # query object:
        if not self.validate(schema):
            raise ValidationError('Unable to validate "%s"' % self.fieldname)
        return query_object(self, schema)

    def _set_value(self, value):
        self._value = value

    def _get_value(self):
        return self._value

    value = property(_get_value, _set_value)

    def validate(self, schema):
        field = self.field(schema)
        if field is None:
            return False
        try:
            field.validate(self.value)
        except ValidationError:
            return False
        return True


class CoreFilter(Persistent):
    """Core persistent record filter implementation"""

    implements(IRecordFilter)

    def __init__(self, *args, **kwargs):
        super(CoreFilter, self).__init__(*args, **kwargs)
        self._uid = str(uuid.uuid4())
        self.reset(**kwargs)

    def reset(self, **kwargs):
        self.operator = kwargs.get('operator', 'AND')
        self._queries = PersistentMapping()
        self._order = PersistentList()

    def validate(self, schema):
        for query in self._queries.values():
            if not query.validate(schema):
                raise ValidationError(query.fieldname)

    def build(self, schema):
        self.validate(schema)
        return filter_query(self, schema)

    def add(self, query=None, **kwargs):
        if query is None:
            ## attempt to make query from kwargs given either
            ## field/comparator/value or fieldname/comparator/value
            field = kwargs.get('field', None)
            fieldname = kwargs.get('fieldname', None)
            if not (field or fieldname):
                raise ValueError('Field missing for query construction')
            if fieldname is None and field:
                fieldname = field.__name__
            comparator = kwargs.get('comparator', None)
            value = kwargs.get('value', None)
            if not (value and comparator):
                raise ValueError('Missing value or comparator')
            query = FieldQuery(fieldname, comparator, value)
        fieldname = query.fieldname
        self._queries[fieldname] = query
        self._order.append(fieldname)

    def remove(self, query):
        if IFieldQuery.providedBy(query):
            query = query.fieldname
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


class BaseGroup(PersistentList):

    def __init__(self, operator='union', items=()):
        self.operator = operator
        # UUID is relevant to FilterGroup, safe to ignore on ComposedQuery
        self._uid = str(uuid.uuid4())
        super(BaseGroup, self).__init__(items)

    def reset(self):
        self.operator = 'union'  # default
        while len(self) > 0:
            self.pop()

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

    def build(self, schema):
        """construct a repoze.catalog query"""
        return grouped_query(self, schema)


class FilterGroup(BaseGroup):

    implements(IFilterGroup)


class ComposedQuery(BaseGroup):
    
    implements(IComposedQuery)

    def __init__(self, name, operator='union', items=()):
        super(ComposedQuery, self).__init__(operator, items)
        self.name = str(name)

    def requires_advanced_editing(self):
        """
        Returns True/False for UI use; see IComposedQuery docs.
        """
        if len(self) > 1:
            return True
        if len(self) == 0:
            return False
        if len(self[0]) > 1:
            return True
        return False


# JSON Adapters for filter, group, composed query:

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
            queries.append(FieldQuery(fieldname, comparator, value))
        self.context.reset()  # clear queries
        self.context.operator = data.get('operator', 'AND')
        r = map(self.context.add, queries)  # add all  # noqa

    def _serialize_value(self, field, value):
        if value and fieldtypes.IDate.providedBy(field):
            return value.strftime('%Y-%m-%d')
        return value

    def _mkrow(self, query):
        field = query.field(self.schema)
        row = {}
        row['fieldname'] = query.fieldname
        row['value'] = self._serialize_value(field, query.value)
        row['comparator'] = query.comparator
        return row

    def serialize(self, use_json=True, include_uid=False):
        """
        Serialze queries of context to JSON, or if use_json is False, to an
        equivalent dict of data.
        """
        data = {}
        if include_uid:
            data['uid'] = IUUID(self.context)
        data['operator'] = self.context.operator
        data['rows'] = [self._mkrow(q) for q in self.context.values()]
        if use_json:
            return json.dumps(data, indent=4)
        return data


class FilterGroupJSONAdapter(object):

    def __init__(self, context, schema):
        if not IFilterGroup.providedBy(context):
            raise ValueError('context must provide IFilterGroup')
        if not IInterface.providedBy(schema):
            raise ValueError('schema provided must be interface')
        self.context = context
        self.schema = schema

    def update(self, data):
        if isinstance(data, basestring):
            data = json.loads(data)
        self.context.reset()
        self.context.operator = str(data.get('operator', 'union'))
        for filter_spec in data.get('filters', []):
            rfilter = CoreFilter()
            self.context.append(rfilter)
            FilterJSONAdapter(rfilter, self.schema).update(filter_spec)

    def _filterJSON(self, f):
        adapter = FilterJSONAdapter(f, self.schema)
        return adapter.serialize(
            use_json=False,
            include_uid=True,
            )

    def serialize(self, use_json=True):
        data = {}  # ComposedQuery
        data['uid'] = IUUID(self.context)
        data['operator'] = self.context.operator  # set operator
        data['filters'] = map(self._filterJSON, list(self.context))
        if use_json:
            return json.dumps(data, indent=4)
        return data


class ComposedQueryJSONAdapter(object):
    """
    Adapter to create and marshal JSON from an IComposedQuery object.
    """
    
    def __init__(self, context, schema):
        if not IComposedQuery.providedBy(context):
            raise ValueError('context must provide IComposedQuery')
        if not IInterface.providedBy(schema):
            raise ValueError('schema provided must be interface')
        self.context = context
        self.schema = schema

    def update(self, data):
        if isinstance(data, basestring):
            data = json.loads(data)
        self.context.reset()
        self.context.operator = str(data.get('operator', 'union'))
        for group_spec in data.get('groups', []):
            group = FilterGroup()
            self.context.append(group)
            FilterGroupJSONAdapter(group, self.schema).update(group_spec)

    def _groupJSON(self, g):
        return FilterGroupJSONAdapter(g, self.schema).serialize(use_json=0)

    def serialize(self, use_json=True):
        data = {}  # ComposedQuery
        data['name'] = self.context.name
        data['operator'] = self.context.operator  # set operator
        data['groups'] = map(self._groupJSON, list(self.context))
        if use_json:
            return json.dumps(data, indent=4)
        return data


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
    """Scaffolding: query contains group contains (empty) filter"""
    f = CoreFilter()
    g = FilterGroup(items=(f,))
    q = ComposedQuery(name, items=(g,))
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
        # note: may write on otherwise read-txn for BBB
        setattr(context, _attr, composed_storage())
        transaction.get().note('Added composed query storage to measure')
    return getattr(context, _attr).get(name)

    
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

