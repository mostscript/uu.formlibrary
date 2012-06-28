from plone.directives import form
from plone.formwidget.contenttree import ContentTreeFieldWidget
from plone.formwidget.contenttree.source import UUIDSourceBinder
from zope.interface import Interface, Invalid, invariant
from zope.interface.common.mapping import IIterableMapping
from zope.publisher.interfaces import IPublishTraverse
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm


API_VERSION = 1
COMPARATORS = (
    'All',
    'Any',
    'Contains',
    'DoesNotContain',
    'Eq',
    'Ge',
    'Gt',
    'InRange',
    'Le',
    'Lt',
    'NotEq',
    'NotInRange',
    )
COMPARATOR_VOCABULARY = SimpleVocabulary(
    [SimpleTerm(k) for k in COMPARATORS]
    )


class ISearchAPICapability(IPublishTraverse):
    """
    Interface for an API capability that is an object-published
    component.
    """
    
    def __call__(*args, **kwargs):
        """
        return simple Python data structure such as dict,
        list, or if necessary a specific component for the
        capability.
        """
    
    def index_html(self, REQUEST=None):
        """
        Return JSON representation of data returned from call.
        Used over-the-web for HTTP APIs.
        """


class IComparator(Interface):
    """An individual comparator's metadata."""
    
    name = schema.TextLine(
        title=u'Comparator name',
        description=u'Identifier for comparator.',
        required=True,
        )
    
    label = schema.TextLine(
        title=u'Label',
        description=u'Label or title for comparator; displayed in forms; '\
                    u'this is typically a verb/predicate phrase.',
        required=False,
        )
    
    description = schema.Text(
        title=u'Description',
        description=u'Description or help text for comparator.',
        required=False,
        )
    
    symbol = schema.TextLine(
        title=u'Unicode symbol',
        description=u'One or a few characters of Unicode text '\
                    u'representing an operator symbol or glyph.',
        required=False,
        )



class IComparators(ISearchAPICapability, IIterableMapping):
    """Mapping interface listing comparator metadata."""
    
    def keys():
        """Names of comparators as unicode objects."""
    
    def __getitem__(name):
        """Get a comparator by name providing IComparator"""



class ISearchableFields(ISearchAPICapability, IIterableMapping):
    """
    Mapping interface for obtaining field names, comparators and
    metadata for a field, and widget and/or vocabularies.
    """


class ISearchAPI(IIterableMapping, IPublishTraverse):
    """
    Search API interface: common API for over-the-web (JSON) use and 
    use in Python.  This interface is an entry point for specific
    search-related capabililties for querying uu.formlibrary form data
    and constructing search forms (dynamically, usually via JavaScript)
    for query construction.
    
    Has mapping interface listing names of capabilities, along with 
    capability object values.
    """
    
    version = schema.Int(
        readonly=True,
        default=API_VERSION,
        )
    
    comparators = schema.Object(
        title=u'Comparators',
        description=u'Comparators metadata capability; this is, '\
                    u'in theory, independent of the context.',
        schema=IComparators,
        )
    
    fields = schema.Object(
        title=u'Searchable fields',
        description=u'Field information metadata capability, '\
                    u'dependent on context for schema information.',
        schema=ISearchableFields,
        )
    
    def __call__(*args, **kwargs):
        """
        Return text string 'Form search API' plus version, along
        with a human-readable listing of capability names 
        ('comparators', 'fields', etc).
        """


class IFieldQuery(Interface):
    """Represent query of a single field"""
    
    field = schema.Object(
        title=u'Field',
        description=u'Field on schema for some context.',
        required=True,
        schema=schema.interfaces.IField,
        )
    
    comparator = schema.Choice(
        title=u'Comparator',
        vocabulary=COMPARATOR_VOCABULARY,
        required=True,
        )
    
    value = schema.Object(
        title=u'Query value',
        schema=Interface,
        required=True,
        )  # arbitrary, duck-typed value
    
    def validate(iface):
        """
        Given an interface, validate that the configured field
        name / type / value_type are included in the interface.  May
        be used for generating warnings to users about compatibility
        of a query with an interface.
        """


class IBaseFilter(form.Schema):
    """Base interface for filters"""
    
    title = schema.TextLine(
        title=u'Title',
        description=u'Title or name of filter.',
        required=True,
        )
    
    description = schema.Text(
        title=u'Description',
        required=False,
        )
    
    def __call__(context):
        """
        Given a context of a form, return a matching result set for the
        filter applied.
        """


class IRecordFilter(IBaseFilter):
    """
    A record filter is a named item that stores a set of field queries
    for use on a search context.
    """
    
    operator = schema.Choice(
        title=u'Cross-field operator',
        description=u'Choose AND (intersection) or OR (union) for combining '\
                    u'results of each field query.',
        vocabulary=SimpleVocabulary(map(lambda t: SimpleTerm(t), ('AND', 'OR'))),
        default='AND',
        )
    
    # query is not maintained in edit form of record filter, needs own 
    # view for editing, because the three primary fields of IFieldQuery
    # are sequentially defined (contingent) and a JavaScript implementation
    # using the filters/comparators APIs is more sensible.
    form.omitted('queries')
    queries = schema.List(
        title=u'Queries',
        description=u'List of IFieldQuery objects, one or more per field.',
        value_type=schema.Object(schema=IFieldQuery),
        )
    
    def validate():
        """
        For the given schema context, validate each query in self.queries,
        using the validate(iface) method of each query object and the 
        interface/schema bound to the context of this filter.
        """


class ICompositeFilter(IBaseFilter):
    """A composite filter """
    
    form.widget(filter_a=ContentTreeFieldWidget)
    filter_a = schema.Choice(
        title=u'Filter A',
        description=u'The first filter to consider for set operations.',
        source=UUIDSourceBinder(object_provides=IRecordFilter.__identifier__),
        required=True,
        )
    
    form.widget(filter_b=ContentTreeFieldWidget)
    filter_b = schema.Choice(
        title=u'Filter B',
        description=u'The first filter to consider for set operations.',
        source=UUIDSourceBinder(object_provides=IRecordFilter.__identifier__),
        required=True,
        )
    
    set_operator = schema.Choice(
        title=u'Set operation',
        description=u'The operation to perform to compute a given result '\
                    u'set from the results of two specified filters.',
        vocabulary=SimpleVocabulary(
            map(lambda s:SimpleTerm(value=s[0], title=s[1]),
                [('union', u'\u222a Union (OR)'),
                 ('intersection', u'\u2229 Intersection (AND)'),
                 ('difference', u'Relative complement (A\\B \u2261 A\u2212B)'),
                ],
                )
            ),
        default='union',
        )
    
    @invariant
    def distinct_filters(data):
        if data.filter_a and data.filter_b:
            if data.filter_a == data.filter_b:
                raise Invalid('Filters A and B must be distinct, not same.')


class IJSONFilterRepresentation(Interface):
    """
    Adapter interface for updating/serializing context from JSON matching:

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
    
    def update(data):
        """Given JSON or dict matching above format, update context"""
    
    def serialize(json=True):
        """
        Output JSON representation (or if json is False, a dict) of
        the filter queries for context.
        """

