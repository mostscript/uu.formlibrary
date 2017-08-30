import operator

from Acquisition import aq_parent, aq_inner
from five import grok
from plone.app.layout.navigation.interfaces import INavigationRoot
from plone.autoform import directives
from plone.supermodel import model
from plone.uuid.interfaces import IAttributeUUID, IUUID
from z3c.form.browser.radio import RadioFieldWidget
from zope.component.hooks import getSite
from zope.container.interfaces import IOrderedContainer
from zope.interface import Interface, Invalid, implements, invariant
from zope.interface.common.mapping import IWriteMapping, IIterableMapping
from zope import schema
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from uu.formlibrary.browser.widget import CustomRootRelatedWidget
from uu.formlibrary.browser.widget_overrides import TypeADateFieldWidget
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.interfaces import local_definitions
from uu.formlibrary.interfaces import navroot_for

from uu.formlibrary.utils import local_query
from uu.formlibrary.vocabulary import definition_field_source
from uu.formlibrary.vocabulary import definition_flex_datasource_fields


# global constants:

MEASURE_DEFINITION_TYPE = 'uu.formlibrary.measure'
GROUP_TYPE = 'uu.formlibrary.measuregroup'
DATASET_TYPE = 'uu.formlibrary.setspecifier'

# vocabularies:

FLEX_LABEL = u'Flex form (each form instance is a single record)'

MR_LABEL = u'Multi-record form (e.g. chart review)'

SOURCE_TYPE_CHOICES = SimpleVocabulary([
    SimpleTerm(SIMPLE_FORM_TYPE, title=FLEX_LABEL),
    SimpleTerm(MULTI_FORM_TYPE, title=MR_LABEL),
])


MR_FORM_COMMON_FILTER_CHOICES = [
    SimpleTerm('multi_total', title=u'Total records (multi-record form)'),
    SimpleTerm(
        'multi_filter',
        title=u'Value computed by a filter of records',
        ),
    SimpleTerm('multi_metadata', title=u'Metadata field value'),
    SimpleTerm(
        'multi_summarize',
        title=u'Summarize numeric values from within multiple records',
        ),
]

MR_FORM_NUMERATOR_CHOICES = SimpleVocabulary(MR_FORM_COMMON_FILTER_CHOICES)

MR_FORM_DENOMINATOR_CHOICES = SimpleVocabulary(
    [
        SimpleTerm(
            'constant',
            title=u'No denominator (do not divide numerator value)'
        ),
    ] + MR_FORM_COMMON_FILTER_CHOICES,
)


VALUE_TYPE_CHOICES = SimpleVocabulary([
    SimpleTerm(value=v, title=title)
    for v, title in (
        ('count', u'Count of occurrences'),
        ('decimal', u'Decimal number, including ratio value.'),
        ('percentage', u'Percentage of total or selected records'),
        ('rating', u'Rating on a scale'),
        )
    ]
)


ROUNDING_CHOICES = SimpleVocabulary([
    SimpleTerm('', title=u'No rounding -- do not modify value'),
    SimpleTerm('round', title=u'Round (up/down)'),
    SimpleTerm('ceiling', title=u'Ceiling: always round upward.'),
    SimpleTerm('floor', title=u'Floor: always round downward.'),
])


CUMULATIVE_CHOICES = SimpleVocabulary([
    SimpleTerm('', title=u'Not cumulative'),
    SimpleTerm('numerator', title=u'Apply to computed numerator'),
    # SimpleTerm('denominator', title=u'Apply to computed denominator.'),
    # SimpleTerm(
    #     'both',
    #     title=u'Apply to both numerator, denominator respectively.',
    #     ),
    # SimpleTerm('final', title=u'Apply to final value for each period.'),
])


F_MEAN = lambda l: float(sum(l)) / len(l) if len(l) > 0 else float('nan')


def F_MEDIAN(l):
    """
    Return middle value of sorted sequence for an odd-sized
    list, or return the arithmetic mean of the two middle-values
    in an even-sized list.
    """
    odd = lambda v: bool(v % 2)
    s, size = sorted(l), len(l)
    middle = size / 2
    _slice = slice((middle - 1), (middle + 1))
    return s[middle] if odd(size) else F_MEAN(s[_slice])


AGGREGATE_FUNCTIONS = {
    'SUM': sum,
    'DIFFERENCE': lambda s: reduce(lambda a, b: a - b, s),
    'AVG': F_MEAN,
    'PRODUCT': lambda l: reduce(operator.mul, l),
    'RATIO': lambda s: reduce(lambda a, b: a / float(b), s),
    'MIN': min,
    'MAX': max,
    'MEDIAN': F_MEDIAN,
    'COUNT': len,
    'FIRST': lambda seq: seq[0] if len(seq) else None,
    'LAST': lambda seq: seq[-1] if len(seq) else None,
}

AGGREGATE_LABELS = [
    ('SUM', u'Sum'),
    ('DIFFERENCE', u'Difference'),
    ('AVG', u'Average'),
    ('PRODUCT', u'Product'),
    ('RATIO', u'Ratio'),
    ('MIN', u'Minimum'),
    ('MAX', u'Maximum'),
    ('MEDIAN', u'Median'),
    ('COUNT', u'Count of occurrences'),
    ('FIRST', u'Pick first found value'),
    ('LAST', u'Pick last found value'),
]

CUMULATIVE_FN_CHOICES = SimpleVocabulary(
    [SimpleTerm(v, title=title) for v, title in AGGREGATE_LABELS]
)


class PermissiveVocabulary(SimpleVocabulary):
    def __contains__(self, value):
        return True

    def getTermByToken(self, token):
        """
        this works around z3c.directives.widget.SequenceWidget.extract()
        pseudo-validation (which is broken for a permissive vocabulary).
        """
        try:
            v = super(PermissiveVocabulary, self).getTermByToken(token)
        except LookupError:
            # fallback using dummy term, assumes token==value
            return SimpleTerm(token)
        return v


class MeasureGroupContentSourceBinder(object):
    """
    Source binder for listing items contained in measure group parent of
    a measure context, filtered by type.
    """

    implements(IContextSourceBinder)

    def __init__(self, portal_type=None, exclude_context=True):
        self.typename = str(portal_type)
        self.exclude_context = exclude_context

    def _group(self, context):
        while not INavigationRoot.providedBy(context):
            if IMeasureGroup.providedBy(context):
                return context
            context = aq_parent(aq_inner(context))
        return None

    def __call__(self, context):
        group = self._group(context)
        if group is None:
            return PermissiveVocabulary([])
        contained = group.objectValues()
        if self.typename:
            contained = filter(
                lambda o: o.portal_type == self.typename,
                contained,
                )
        if self.exclude_context:
            _idmatch = lambda o: o.getId() == context.getId()
            _groupcontext = IMeasureGroup.providedBy(context)
            contained = filter(
                lambda o: _groupcontext or not _idmatch(o),
                contained,
            )
        terms = map(
            lambda o: SimpleTerm(IUUID(o), title=o.Title().decode('utf-8')),
            contained,
            )
        return PermissiveVocabulary(terms)


# Sources: all content in navroot, respectively (via catalog)...
#  -- note: used by uu.chart

def _search(query):
    return getSite().portal_catalog.unrestrictedSearchResults(query)


def find_in_navroot(context, portal_type):
    site, navroot = navroot_for(context)
    query = local_query(navroot, {}, types=(portal_type,), depth=-1)
    return _search(query)


def brain_title(brain, parent_suffix=False):
    if not parent_suffix:
        return brain.Title
    parent_name = brain.getPath().split('/')[-2]
    return u'%s \u2003(%s)' % (brain.Title, parent_name)


def content_vocab(result, parent_suffix=False):
    return SimpleVocabulary([
        SimpleTerm(
            brain.UID,
            title=brain_title(brain, parent_suffix)
            ) for brain in result
        ])


@grok.provider(IContextSourceBinder)
def all_measures_in_navroot(context):
    return content_vocab(
        find_in_navroot(context, MEASURE_DEFINITION_TYPE),
        True
        )


@grok.provider(IContextSourceBinder)
def all_datasets_in_navroot(context):
    return content_vocab(
        find_in_navroot(context, DATASET_TYPE),
        True
        )


# core interfaces (shared by content types and/or forms):

class IMeasureNaming(model.Schema):
    """Title, description naming for measure."""

    title = schema.TextLine(
        title=u'Name (title) of measure',
        required=True,
        )

    description = schema.Text(
        title=u'Describe your measure (optional)',
        required=False,
        )


class IMeasureFormDefinition(model.Schema):
    """Bound form definition for a measure group"""

    definition = schema.Choice(
        title=u'Select a form definition',
        description=u'Select a form definition to use for measure(s). '
                    u'The definition that you choose will control the '
                    u'available fields for query by measure(s).',
        source=local_definitions,
        required=True,
        )


class IMeasureSourceType(model.Schema):
    """Choose form data-source type"""

    directives.widget(source_type=RadioFieldWidget)
    source_type = schema.Choice(
        title=u'Data source type',
        description=u'What kind of form data will provide a data source '
                    u'used to compute measure values?',
        vocabulary=SOURCE_TYPE_CHOICES,
        default=MULTI_FORM_TYPE,
        required=True,
        )


class IMeasureCalculation(model.Schema):
    """Numerator/denominator selection for measure via multi-record form"""

    directives.widget(numerator_type=RadioFieldWidget)
    numerator_type = schema.Choice(
        title=u'Computed value: numerator',
        description=u'Choose how the core computed value is obtained.',
        vocabulary=MR_FORM_NUMERATOR_CHOICES,
        default='multi_filter',
        required=True,
        )

    directives.widget(denominator_type=RadioFieldWidget)
    denominator_type = schema.Choice(
        title=u'(Optional) denominator',
        description=u'You may choose if and how an optional denominator is '
                    u'used to compute this measure.  The default '
                    u'denominator is the total of records for a given form, '
                    u'which is useful for percentages and ratios, but you '
                    u'may also choose a constant denominator if what you '
                    u'aim to compute and display is a raw count of matches '
                    u'resulting from a numerator computed by filter.',
        vocabulary=MR_FORM_DENOMINATOR_CHOICES,
        default='multi_total',
        required=True,
        )

    @invariant
    def sensible_nm(data):
        nt, mt = data.numerator_type, data.denominator_type
        if (nt == mt) and nt in ('multi_total', 'constant'):
            # 1/1 == N/N == 1 -- this is nonsense value
            m = 'Numerator, denominator types selected will always lead '\
                'to a value equal to one, this is neither useful or allowed.'
            raise Invalid(m)


class IMeasureRounding(model.Schema):

    display_precision = schema.Int(
        title=u'Digits after decimal point (display precision)?',
        description=u'When displaying a decimal value, how many places '
                    u'beyond the decimal point should be displayed in '
                    u'output?  Default: two digits after the decimal point.',
        default=1,
        )

    directives.widget(rounding=RadioFieldWidget)
    rounding = schema.Choice(
        title=u'How should number be optionally rounded?',
        description=u'You may choose to round decimal values to integer '
                    u'(whole or negative non-decimal number) values using '
                    u'a rounding rule; be default, no rounding takes '
                    u'place.  You may prefer to use display precision '
                    u'above in many cases, instead of rounding.',
        vocabulary=ROUNDING_CHOICES,
        required=False,
        default='',
        )


class IMeasureUnits(model.Schema):
    """Modifiers for computed value: units, multiplier, rounding rules"""

    directives.widget(value_type=RadioFieldWidget)
    value_type = schema.Choice(
        title=u'Kind of value',
        description=u'What are the basic units of measure?',
        vocabulary=VALUE_TYPE_CHOICES,
        required=True,
        )

    multiplier = schema.Float(
        title=u'Value multiplier constant',
        description=u'What constant numeric (whole or decimal number) '
                    u'should the raw computed value be multiplied by?  For '
                    u'percentages computed with both a numerator and '
                    u'denominator, enter 100.',
        default=1.0,
        )

    units = schema.TextLine(
        title=u'Units of measure',
        description=u'Label for units of measure (optional).',
        required=False,
        )


class IMeasureFieldSpec(model.Schema):
    """
    Field specification for flex/simple form measures with values
    sourced directly from form field values, or for values summarized from
    multi-record forms via a function.
    """

    numerator_field = schema.Choice(
        title=u'Numerator field',
        description=u'Which form field provides the numerator value? If '
                    u'no value is specified, no numerator will be used.',
        source=definition_flex_datasource_fields,
        default='',
        )

    denominator_field = schema.Choice(
        title=u'Denominator field',
        description=u'Which form field provides a denominator value?  If '
                    u'this is unspecified, no denominator will be used.',
        source=definition_flex_datasource_fields,
        default='',
        )

    notes_field = schema.Choice(
        title=u'Notes field',
        description=u'Which form field may provide note(s) for this measure. '
                    u'(optional)',
        source=definition_field_source,
        default='',
        )

    summarization_numerator = schema.Choice(
        title=u'Summarization function (numerator)',
        description=u'Function to summarize numeric values from records '
                    u'of a multi-record form, if applicable: numerator.',
        vocabulary=CUMULATIVE_FN_CHOICES,
        default='AVG',
        )

    summarization_denominator = schema.Choice(
        title=u'Summarization function (denominator)',
        description=u'Function to summarize numeric values from records '
                    u'of a multi-record form, if applicable: denominator.',
        vocabulary=CUMULATIVE_FN_CHOICES,
        default='AVG',
        )


class IMeasureCumulative(model.Schema):
    """
    Cumulative calculation configuration options applicable
    to time-series.
    """

    cumulative = schema.Choice(
        title=u'Cumulative calculation?',
        description=u'Should values in series be cumlatively calculated?',
        vocabulary=CUMULATIVE_CHOICES,
        default='',
        required=False,
        )

    cumulative_fn = schema.Choice(
        title=u'Cumulative function (if applicable)',
        vocabulary=CUMULATIVE_FN_CHOICES,
        default='SUM',
        )


# content type interfaces:

class IMeasureDefinition(model.Schema,
                         IAttributeUUID,
                         IMeasureNaming,
                         IMeasureCalculation,
                         IMeasureRounding,
                         IMeasureFieldSpec,
                         IMeasureCumulative,
                         IMeasureUnits):
    """
    Measure definition content interface.

    Note: measures get their bound form definition and data source
    type from the measure group containing them.

    There is a pretty safe assumption that a measure value should
    be a floating point number.
    """

    model.fieldset(
        'multi_record',
        label=u'Multi-record form calculation',
        fields=['numerator_type', 'denominator_type'],
        )

    model.fieldset(
        'flex_calc',
        label=u'Field value calculation',
        fields=[
            'numerator_field',
            'denominator_field',
            'notes_field',
            'summarization_numerator',
            'summarization_denominator',
            ]
        )

    model.fieldset(
        'advanced',
        label=u'Advanced',
        fields=['cumulative', 'cumulative_fn'],
        )

    goal = schema.Float(
        title=u'Goal value',
        description=u'Numeric value of goal, if applicable (optional).',
        required=False,
        )

    def group():
        """Get parent group containing this measure"""

    def value_for(context):
        """
        Given an appropriate form context, compute a value, normalize
        as appropriate (for .
        """

    def display_format(value):
        """
        Format a value as a string using rules defined on measure
        definition.
        """

    def display_value(context):
        """
        Return string display value (formatted) for context.
        """

    def datapoint(context):
        """
        Given a form instance as a context, apply measure
        to get a data point (info dict).
        """

    def points(seq):
        """
        Given a sequence of form instances, get data-point
        for each by applying measure function, preserving
        sort order.
        """

    def dataset_points(dataset):
        """
        Given a topic/collection object, get all form instances
        matching that topic, and get a data-point for each,
        preserving sort order.
        """

    def value_note(info):
        """
        Given an info dict (data point), construct note text as
        a unicode object if applicable, or return None.
        """


class IMeasureGroup(model.Schema,
                    IAttributeUUID,
                    IMeasureFormDefinition,
                    IMeasureSourceType,
                    ):
    """
    Measure group (folderish) content interface.  Measure groups
    contain both measure and common topic/collection/dataset items
    used by all measures contained within.
    """


class IMeasureLibrary(model.Schema, IOrderedContainer, IAttributeUUID):
    """
    Marker interface for library folder containing measure groups, which
    contain measure definitions (and topic/collections as data sets).
    """


# data set interfaces:

class IFormDataSetSpecification(model.Schema):
    """
    Query specification for filtering a set of forms, and methods
    to obtain iterable of forms or brains for forms matching the
    specification.
    """

    model.fieldset(
        'filters',
        label=u'Query filters',
        fields=[
            'query_title',
            'query_subject',
            'query_state',
            'query_start',
            'query_end',
            ]
        )

    model.fieldset(
        'aggregation',
        label=u'Aggregation',
        fields=[
            'use_aggregate',
            'aggregate_datasets',
            'aggregate_function',
            ]
        )

    directives.widget(query_start=TypeADateFieldWidget)
    directives.widget(query_end=TypeADateFieldWidget)

    title = schema.TextLine(
        title=u'Title',
        description=u'Name of form set.',
        required=True,
        )

    description = schema.Text(
        title=u'Description',
        description=u'Description of the form set resulting from '
                    u'selection or query.',
        required=False,
        )

    # locations can be specific forms or series, or parent* folders
    directives.widget(
        'locations',
        CustomRootRelatedWidget,
        pattern_options={'mode': 'auto'},
        # ideally, we would use found navigation root as rootPath,
        # not basePath, so that browsing cannot escape nav root;
        # However, this bug must be fixed first:
        #   https://github.com/plone/mockup/issues/795
        #   -- if this gets fixed, we would want to set below to False...
        use_base=True,
        # custom root query kicks widget to use nav-root as basePath
        custom_root_query={
            'object_provides':
                'plone.app.layout.navigation.interfaces.INavigationRoot'
            }
        )
    locations = schema.List(
        title=u'Included locations',
        description=u'Select locations (specific forms or containing '
                    u'folders, including form series and/or parent '
                    u'folders) to include.  If you do not choose at '
                    u'least one location, all forms will be included and '
                    u'optionally filtered. If you choose locations, only '
                    u'forms within those locations will be included and '
                    u'optionally filtered by any chosen filter criteria.',
        value_type=schema.BytesLine(),
        required=False,
        defaultFactory=list,
        )

    sort_on_start = schema.Bool(
        title=u'Sort on start date?',
        description=u'Should resulting forms included be sorted by '
                    u'their respective start dates?',
        required=False,
        default=True,
        )

    query_title = schema.TextLine(
        title=u'Filter: title',
        description=u'Full text search of title of forms.',
        required=False,
        )

    query_subject = schema.List(
        title=u'Filter: tags',
        description=u'Query for any forms matching tags or subject '
                    u'(one per line).',
        value_type=schema.TextLine(),
        required=False,
        defaultFactory=list,  # req zope.schema >= 3.8.0
        )

    query_state = schema.List(
        title=u'Filter: workflow state(s)',
        description=u'List of workflow states. If not specified, items in '
                    u'any state will be considered.',
        value_type=schema.Choice(
            vocabulary=u'plone.app.vocabularies.WorkflowStates',  # named vocab
            ),
        required=False,
        defaultFactory=list,  # req zope.schema >= 3.8.0
        )

    query_start = schema.Date(
        title=u'Filter: date range start',
        description=u'Date range inclusion query (start).',
        required=False,
        )

    query_end = schema.Date(
        title=u'Filter: date range end',
        description=u'Date range inclusion query (end).',
        required=False,
        )

    use_aggregate = schema.Bool(
        title=u'Use aggregate calculation?',
        description=u'If selected, and other data-sets are selected '
                    u'for aggregation, calculate aggregate value '
                    u'for these data-sets using function specified?',
        default=False,
        )

    aggregate_datasets = schema.List(
        title=u'Aggregate data-sets',
        value_type=schema.Choice(
            source=MeasureGroupContentSourceBinder(portal_type=DATASET_TYPE),
            ),
        defaultFactory=list,
        required=False,
        )

    aggregate_function = schema.Choice(
        title=u'Aggregate function',
        vocabulary=CUMULATIVE_FN_CHOICES,
        default='AVG',
        )

    def brains(self):
        """Return an iterable of catalog brains for forms included."""

    def forms(self):
        """Return an iterable of form objects included."""

    def included_locations(self):
        """
        List of catalog brains of included locations in locations field.
        """

    def directly_included(self, spec):
        """
        Given spec as either UID, form object, or brain, return True if
        the form object is directly included in the locations field, or
        return False if merely indirectly included.
        """


# adapter interfaces

class IMultiRecordMeasureFactory(Interface):
    """Adapter interface for content creation"""

    def __call__(data):
        """Create measures based on wizard data, see wizard.py"""


class IDataPointCache(IIterableMapping, IWriteMapping):
    """
    A global component that acts as a mapping of
    tuple keys to datapoint mapping values, such that:

        * Keys are four-item tuples, with:
            - Measure UID
            - Measure modified date (ISO 8601 string date stamp)
            - Form UID
            - Form modified date (ISO 8601 string date stamp)
        * Values are datapoint mappings, such as a dict or
          PersistentMapping.

    Assume that this component has access to local site, whether
    as a utility component using zope.component.hooks.getSite()
    or as an adapter of the site.

    All writes to this cache are done by the cache component itself,
    via reload() or invalidate() -- or explicitly by callers using
    the equivalent store() or __setitem__() methods documented below.
    """

    def select(uid):
        """
        Given UID of form or measure content items, return sequence
        of all cache keys that match the UID of content items.
        """

    def invalidate(uid):
        """
        Given the UID of either a measure or form, invalidate all
        keys using those UIDs.
        """

    def reload(uid):
        """
        Given UID of either a measure or a form, invalidate any
        existing keys for that UID, then load/cache summarized
        datapoints in the cache
        """

    def store(key, value):
        """
        Given a four item tuple as a key, such that keys match
        specification documented for this interface, set key/value
        pair in cache, assuming value is a mapping such as a dict.
        Implementations may re-cast value to PersistentMapping in
        cases where the storage is persistent (ZODB).
        """

    def __setitem__(key, value):
        """Alterate spelling for store(); validates accordingly."""

    def __delitem__(key):
        """
        Explicitly remove a four-item tuple key; validates key
        before attempting to remove; key not found or invalid keys
        will result in a raised KeyError.
        """

