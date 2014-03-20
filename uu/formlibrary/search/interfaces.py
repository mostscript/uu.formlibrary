from plone.uuid.interfaces import IUUIDAware
from zope.interface import Interface
from zope.interface.common.mapping import IIterableMapping
from zope.interface.common.sequence import ISequence
from zope.publisher.interfaces import IPublishTraverse
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from uu.formlibrary.interfaces import DEFINITION_TYPE  # noqa


API_VERSION = 1

FILTER_TYPE = 'uu.formlibrary.recordfilter'

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

    def index_html(REQUEST=None):
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
        description=u'Label or title for comparator; displayed in forms; '
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
        description=u'One or a few characters of Unicode text '
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
        description=u'Comparators metadata capability; this is, '
                    u'in theory, independent of the context.',
        schema=IComparators,
        )

    fields = schema.Object(
        title=u'Searchable fields',
        description=u'Field information metadata capability, '
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
    """
    Represent query of a single field.  A field query is incomplete without
    application to a specific schema, which is bound late in the build()
    and validate() methods of the field query.
    """

    fieldname = schema.Object(
        title=u'Field name',
        description=u'Field name on schema for some context.',
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

    def field(schema):
        """
        Get associated field named by self.fieldname in the passed
        schema interface.  Returns None if fieldname is not found.
        """

    def build(schema):
        """
        Construct and return a repoze.catalog query object for the
        field query, given a schema to apply it to; returned query
        will always be a comparator query, not a boolean operation.
        Should validate self.value against bound schema, and raise
        a ValidationError if there are issues with the saved query
        value.
        """

    def validate(schema):
        """
        Given an schema, validate that the fieldname for this query
        is known to the schema passed, and that self.value is a
        valid value for that field; returns boolean.
        """


class IRecordFilter(IIterableMapping, IUUIDAware):
    """
    A record filter is a named item that stores a set of field queries
    for use on a search context -- this component represents queries as
    a read-only mapping of fieldname keys and IFieldQuery object values,
    meaning only one field per filter is supported.  Adding and removal
    of queries is possible via methods below.
    """

    operator = schema.Choice(
        title=u'Cross-field operator',
        description=u'Choose AND (intersection) or OR (union) for combining '
                    u'results of each field query.',
        vocabulary=SimpleVocabulary(
            map(lambda t: SimpleTerm(t), ('AND', 'OR'))
            ),
        default='AND',
        )

    def reset():
        """
        Empty filter contents of all queries and set operator to
        default of 'AND'.
        """

    def build(schema):
        """
        Construct and return a repoze.catalog query object for the
        filter and its contained field queries, given a specific schema
        context to apply to.
        """

    def add(query=None, **kwargs):
        """
        Given any of the following, add query to this container:

          * IFieldQuery object as first positional or query argument.
          * keyword arguments of field, value, comparator
          * keyword arguments of field name, value, and comparator.

        In the case of keyword arguments, construct a field query object,
        and persist in this container/mapping component as an additional
        criterion for this filter.
        """

    def remove(query):
        """
        Given query/criterion as IFieldQuery object, or a field name,
        remove said query from containment within this filter.
        """

    def __contains__(name):
        """
        Given name/key (field name) or field query object, return
        True if key or value is contained in this container/mapping,
        otherwise return False.
        """

    def validate(schema):
        """
        For the given schema context, validate each query in self.queries,
        using the validate(schema) method of each query object and the
        interface/schema bound to the context of this filter.
        """


class ISetOperationSpecifier(Interface):
    """Mixin interface for set operation choice"""

    operator = schema.Choice(
        title=u'Set operation',
        description=u'The operation to perform to compute a given result '
                    u'set from the results of two specified filters.',
        vocabulary=SimpleVocabulary(
            map(lambda s: SimpleTerm(value=s[0], title=s[1]),
                [('union', u'\u222a Union (OR)'),
                 ('intersection', u'\u2229 Intersection (AND)'),
                 ('difference', u'Relative complement (A\\B \u2261 A\u2212B)')],
                )
            ),
        default='union',
        )


class IFilterGroup(ISetOperationSpecifier, ISequence, IUUIDAware):
    """
    A group is an iterable, writable sequence of IRecordFilter objects
    that can be composed by a set operation into a query.  Groups are
    identified by UUID.
    """

    def reset():
        """
        Empty filter contents of all queries and set operator to
        default of 'union'.
        """

    def move(item, direction='top'):
        """
        Given item as either UUID for a record filter, or as a filter
        object contained wihtin this group, move its order according
        to the specified direction, which must be one of:
        'up', 'down', 'top', 'bottom'.
        """

    def build(schema):
        """
        Construct and return a repoze.catalog query for this group,
        and all its contained filters, composed using the set operation
        specified for this group.  This is done in the context of the
        schema passed, which is passed to IRecordFilter.build().
        """


class IComposedQuery(ISetOperationSpecifier, ISequence):
    """
    An iterable sequence containing filter groups, with a set operation
    that be specified for use in composing a final query from the
    groups for use in repoze.catalog (when called).

    The composition relationships of all the parts is shown below:

                    IComposedQuery <>-.
                                      :  (sequence)
                .--<> IFilterGroup ---'
    (sequence)  :
                `--- IRecordFilter <>-.
                                      :  (ordered mapping)
                      IFieldQuery ----'
    """

    name = schema.BytesLine(
        title=u'Query name',
        description=u'Query name, either numerator or denominator.',
        constraint=lambda v: str(v) in ('numerator', 'denominator'),
        )

    def reset():
        """
        Empty filter contents of all queries and set operator to
        default of 'union'.
        """

    def move(item, direction='top'):
        """
        Given item as either UUID for a filter group, or as a group
        object contained wihtin this composed query sequence, move its
        order according to the specified direction, which must be one
        of: 'up', 'down', 'top', 'bottom'.
        """

    def build(schema):
        """
        Construct and return a repoze.catalog query for all groups
        by composing the query for each group using the set operation
        specified for this composed query. This is done in the context
        of the schema passed, which is passed to IRecordFilter.build().
        """


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

    The expectation is that one must have an IRecordFilter and a schema
    object to have complete context necessary to construct such JSON.
    """

    def update(data):
        """Given JSON or dict matching above format, update context"""

    def serialize(json=True):
        """
        Output JSON representation (or if json is False, a dict) of
        the filter queries for context.
        """

