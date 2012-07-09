import itertools
import json
from datetime import date

from Acquisition import aq_inner, aq_parent
from zope.component import adapts, adapter
from zope.dottedname.resolve import resolve
from zope.interface import implements, implementer
from zope.publisher.interfaces.browser import IBrowserPublisher
from plone.dexterity.content import Item
from plone.indexer import indexer
from persistent import Persistent
from persistent.dict import PersistentDict
from persistent.list import PersistentList
from zope import schema

from uu.retrieval.utils import identify_interface
from uu.smartdate.converter import normalize_usa_date

from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.search.interfaces import IFieldQuery
from uu.formlibrary.search.interfaces import IJSONFilterRepresentation
from uu.formlibrary.search.interfaces import IRecordFilter, ICompositeFilter

# field serialization, used by FieldQuery:
field_id = lambda f: (identify_interface(f.interface), f.__name__)
resolvefield = lambda t: resolve(t[0])[t[1]]  # (name, fieldname) -> schema


class FieldQuery(Persistent):
    """
    FieldQuery is field / value / comparator entry.  Field is persisted
    using serialization (tuple of dotted name of interface, fieldname),
    but resolution of field object is cached indefinitely in volatile.
    """
    implements(IFieldQuery)
    
    def __init__(self, field, comparator, value):
        if not schema.interfaces.IField.providedBy(field):
            raise ValueError('field provided must be schema field')
        self._field_id = field_id(field)
        self.comparator = str(comparator)
        self.value = value
    
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
    """Given filter, get definition (assumed parent)"""
    return aq_parent(aq_inner(context))


class RecordFilter(Item):
    implements(IRecordFilter)
    
    def __init__(self, id=None, *args, **kwargs):
        super(RecordFilter, self).__init__(id, *args, **kwargs)
        self.reset(**kwargs)
    
    def reset(self, **kwargs):
        self.operator = kwargs.get('operator', 'AND')
        self._queries = PersistentDict()
        self._order = PersistentList()
    
    def schema(self):
        """
        Assume parent/container of RecordFilter always provides schema
        at attribute name of 'schema'.
        """
        definition = IFormDefinition(self)
        return definition.schema
    
    def validate(self):
        schema = self.schema()
        for query in self._queries.values():
            query.validate(schema)
    
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
    
    @property
    def externalEditorEnabled(self):
        return False


class FilterJSONAdapter(object):
    """
    Update/serialize an IRecordFilter object from/to JSON data or
    equivalent dict, matching the destination object format:
        
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
    adapts(IRecordFilter)

    def __init__(self, context):
        if not IRecordFilter.providedBy(context):
            raise ValueError('context must provide IRecordFilter')
        self.context = context
    
    def normalize_value(self, field, value):
        if schema.interfaces.IDate.providedBy(field):
            if isinstance(value, basestring):
                usa_date = normalize_usa_date(value)
                if usa_date is not None:
                    return usa_date  # M/D/YYYY -> date
                return date(*(map(lambda v: int(v), value.split('-'))))  # ISO
        if schema.interfaces.IInt.providedBy(field):
            return int(value)
        if schema.interfaces.IFloat.providedBy(field):
            return float(value)
        return value
    
    def update(self, data):
        """
        Update from JSON data or equivalent dict.
        """
        if isinstance(data, basestring):
            data = json.loads(data)
        queries = []
        for query_row in data.get('rows', []):
            fieldname = query_row.get('fieldname')
            comparator = query_row.get('comparator')
            field = self.context.schema()[fieldname]
            value = self.normalize_value(
                field,
                query_row.get('value'),
                )
            queries.append(FieldQuery(field, comparator, value))
        self.context.reset()  # clear queries
        self.context.operator = data.get('operator', 'AND')
        r = map(self.context.add, queries)  # add all
    
    def _serialize_value(self, field, value):
        if value and schema.interfaces.IDate.providedBy(field):
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


class CriteriaJSONCapability(object):
    """API capability for JSON output"""
    
    implements(IBrowserPublisher)

    def __init__(self, context, request=None):
        self.context = context
        self.request = getRequest() if request is None else request
    
    def __call__(self, *args, **kwargs):
        return FilterJSONAdapter(self.context).serialize(use_json=False)

    def publish_json(self):
        msg = FilterJSONAdapter(self.context).serialize()
        if self.request is not None:
            self.request.response.setHeader('Content-type', 'application/json')
            self.request.response.setHeader('Content-length', str(len(msg)))
        return msg 
    
    def publishTraverse(self, request, name):
        if name == 'publish_json':
            if self.request is not request:
                self.request = request
            return self.publish_json  # callable method
        raise NotFound(self, name, request)
    
    def browserDefault(self, request):
        if request:
            return self, ('publish_json',)
        return self, ()        


class CompositeFilter(Item):
    implements(ICompositeFilter)
    
    @property
    def externalEditorEnabled(self):
        return False


@indexer(ICompositeFilter)
def directly_related_uids(context):
    r = []
    for name in ('filter_a', 'filter_b'):
        v = getattr(context, name, None) or ''
        if len(v) >= 32:
            r.append(v)
    return r
 
