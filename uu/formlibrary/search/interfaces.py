from zope.interface import Interface, Invalid, invariant
from zope.interface.common.mapping import IIterableMapping
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


class IRecordFilter(IIterableMapping):
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

    def validate():
        """
        For the given schema context, validate each query in self.queries,
        using the validate(iface) method of each query object and the
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


class IFilterGroup(ISetOperationSpecifier):
    """
    A group/composite of multiple IRecordFilter objects. In cases
    where more than one filter is a member of this group, a set
    operation can be specified for compositing results.
    """

    filters = schema.Dict(
        title=u'Filters',
        description=u'Ordered mapping of record filters in group, '
                    u'keyed by UUID.',
        key_type=schema.Bytes(description=u'UUID string'),
        value_type=schema.Object(schema=IRecordFilter),
        required=True,
        defaultFactory=list,
        )

    order = schema.List(
        title=u'Filter order',
        description=u'Ordered list of UUIDs to order keys for filters.',
        value_type=schema.Bytes(description=u'UUID string'),
        )

    def __iter__():
        """
        Return iterable of record filters, matching the order specified
        by UUID key in self.order.
        """

    def __len__():
        """
        Return count of filters within.
        """

    def move(uid, direction='top'):
        """
        Move the order of a filter up or down, or to top/bottom
        given an UUID uid for a given filter.  Allowed directions:
        'up', 'down', 'top', 'bottom'.  A full re-order should just
        set self.order on the filter group component rather than
        attempt multiple move() operations.
        """

    @invariant
    def distinct_filters(data):
        if data.filters and len(set(data.filters)) != len(data.filters):
            raise Invalid('There is duplication of filters specified.')


class IFilterGroups(IIterableMapping, ISetOperationSpecifier):
    """
    An iterable mapping of filter groups, with a set operation that can
    be specified for use in composing a single query from the groups.
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
    """

    def update(data):
        """Given JSON or dict matching above format, update context"""

    def serialize(json=True):
        """
        Output JSON representation (or if json is False, a dict) of
        the filter queries for context.
        """

