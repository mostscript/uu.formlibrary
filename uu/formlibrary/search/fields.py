import itertools
import json

from zope.globalrequest import getRequest
from zope.interface import implements
from zope.publisher.interfaces.browser import IBrowserPublisher
from zope.publisher.interfaces import NotFound
from zope.schema import getFieldNamesInOrder

from uu.retrieval.schema import schema_index_types

from uu.formlibrary.interfaces import IFormDefinition
from interfaces import ISearchableFields


_u = lambda v: v if isinstance(v, unicode) else str(v).decode('utf-8')


class FieldInfo(object):

    implements(IBrowserPublisher)

    def __init__(self, field, parent=None, request=None):
        self.field = field
        self.__parent__ = parent
        self.request = request
        self.name = self.__name__ = field.__name__
        self.title = field.title
        self.description = field.description or None
        self.fieldtype = field.__class__.__name__
        self.value_type = getattr(field, 'value_type', None)
        if self.value_type is not None:
            self.value_type = self.value_type.__class__.__name__
        if self.fieldtype == 'Choice':
            self.vocabulary = [t.value for t in field.vocabulary]
        if self.value_type == 'Choice':
            self.vocabulary = [t.value for t in field.value_type.vocabulary]
        self.index_types = schema_index_types(field)

    def __call__(self):
        """Return a dict representation for use in API"""
        keep = (
            'name',
            'title',
            'description',
            'fieldtype',
            'value_type',
            'index_types',
            'vocabulary',
            )
        items = self.__dict__.items()
        return dict([(k, v) for k, v in items if v is not None and k in keep])

    def publish_json(self):
        msg = json.dumps(self(), indent=2)
        if self.request is not None:
            self.request.response.setHeader('Content-type', 'application/json')
            self.request.response.setHeader('Content-length', str(len(msg)))
        return msg

    ## IBrowserPublisher / IPublishTraverse methods:

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


class SearchableFields(object):

    implements(IBrowserPublisher, ISearchableFields)

    def __init__(self, context, request=None):
        ## context should be context of API view, not API view itself
        self.context = context
        self.__parent__ = context  # may be re-parented by API to view
        self.request = getRequest() if request is None else request
        self.definition = IFormDefinition(self.context)
        self._schema = self.definition.schema
        self._fieldnames = getFieldNamesInOrder(self._schema)

    def get(self, name, default=None):
        if name in self._schema:
            return FieldInfo(self._schema[name])
        return default

    def __getitem__(self, name):
        v = self.get(name, None)
        if v is None:
            raise KeyError(name)
        return v

    def __len__(self):
        return len(self._fieldnames)

    def keys(self):
        return self._fieldnames

    def iterkeys(self):
        return self._fieldnames.__iter__()

    def itervalues(self):
        return itertools.imap(lambda k: self.get(k), self.iterkeys())

    def iteritems(self):
        return itertools.imap(lambda k: (k, self.get(k)), self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())

    def __contains__(self, name):
        return name in self._fieldnames

    def __call__(self, *args, **kwargs):
        return dict((k, v()) for k, v in self.iteritems())

    def publish_json(self):
        msg = json.dumps(self(), indent=2)
        if self.request is not None:
            self.request.response.setHeader('Content-type', 'application/json')
            self.request.response.setHeader('Content-length', str(len(msg)))
        return msg

    ## IBrowserPublisher / IPublishTraverse methods:

    def publishTraverse(self, request, name):
        if name == 'publish_json':
            if self.request is not request:
                self.request = request
            return self.publish_json  # callable method
        if name in self._fieldnames:
            return FieldInfo(self._schema[name], parent=self)
        raise NotFound(self, name, request)

    def browserDefault(self, request):
        if request:
            return self, ('publish_json',)
        return self, ()

