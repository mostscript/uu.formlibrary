from plone.directives import form
from plone.formwidget.contenttree import UUIDSourceBinder
from plone.formwidget.contenttree import ContentTreeFieldWidget
from plone.uuid.interfaces import IAttributeUUID
from z3c.form.browser.radio import RadioFieldWidget
from zope.container.interfaces import IOrderedContainer
from zope.globalrequest import getRequest
from zope.interface import Interface
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from uu.formlibrary.interfaces import DEFINITION_TYPE
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE

from utils import find_context

## global constants:

MEASURE_DEFINITION_TYPE = 'uu.formlibrary.measure'
GROUP_TYPE = 'uu.formlibrary.measuregroup'

## vocabularies:

FLEX_LABEL = u'Flex form (each form instance is a single record)'

MR_LABEL = u'Multi-record form (e.g. chart review)'

SOURCE_TYPE_CHOICES = SimpleVocabulary([
    SimpleTerm(SIMPLE_FORM_TYPE, title=FLEX_LABEL),
    SimpleTerm(MULTI_FORM_TYPE, title=MR_LABEL),
])


MR_FORM_FILTER_CHOICES = SimpleVocabulary([
    SimpleTerm('constant', title=u'Constant value (1)'),
    SimpleTerm('multi_total', title=u'Total records (multi-record form)'),
    SimpleTerm(
        'multi_filter',
        title=u'Value computed by a filter of records',
        )
])


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
    SimpleTerm('', title=u'No rounding'),
    SimpleTerm('round', title=u'Round (up/down)'),
    SimpleTerm('ceiling', title=u'Ceiling: always round upward.'),
    SimpleTerm('floor', title=u'Floor: always round downward.'),
])

## field default (defaultFactory) methods:

def default_definition():
    context = find_context(getRequest())  # reconstruct context
    if not context:
        return None
    defn_uid = getattr(context, 'definition', None)
    if defn_uid is None:
        return ''
    return defn_uid


## core interfaces (shared by content types and/or forms):

class IMeasureNaming(form.Schema):
    """Title, description naming for measure."""
    
    title = schema.TextLine(
        title=u'Name (title) of measure',
        required=True,
        )   
    
    description = schema.Text(
        title=u'Describe your measure (optional)',
        required=False,
        )


class IMeasureFormDefinition(form.Schema):
    """Bound form definition for a measure or measure group"""
    
    form.widget(definition=ContentTreeFieldWidget)
    definition = schema.Choice(
        title=u'Select a form definition',
        description=u'Select a form definition to use for measure(s). '\
                    u'The definition that you choose will control the '\
                    u'available fields for query by measure(s).',
        source=UUIDSourceBinder(portal_type=DEFINITION_TYPE),
        required=True,
        defaultFactory=default_definition,
        )


class IMeasureSourceType(form.Schema):
    """Choose form data-source type"""

    form.widget(source_type=RadioFieldWidget)
    source_type = schema.Choice(
        title=u'Data source type',
        description=u'What kind of form data will provide a data source '\
                    u'used to compute measure values?',
        vocabulary=SOURCE_TYPE_CHOICES,
        default=MULTI_FORM_TYPE,
        required=True,
        )


class IMeasureCalculation(form.Schema):
    """Numerator/denominator selection for measure via multi-record form"""
    
    form.widget(numerator_type=RadioFieldWidget)
    numerator_type = schema.Choice(
        title=u'Computed value: numerator',
        description=u'Choose how the core computed value is obtained.',
        vocabulary=MR_FORM_FILTER_CHOICES,
        default='multi_filter',
        required=True,
        )

    form.widget(denominator_type=RadioFieldWidget)
    denominator_type = schema.Choice(
        title=u'(Optional) denominator',
        description=u'You may choose if and how an optional denominator is '\
                    u'used to compute this measure.  The default '\
                    u'denominator is the total of records for a given form, '\
                    u'which is useful for percentages and ratios, but you '\
                    u'may also choose a constant denominator if what you '\
                    u'aim to compute and display is a raw count of matches '\
                    u'resulting from a numerator computed by filter.',
        vocabulary=MR_FORM_FILTER_CHOICES,
        default='multi_total',
        required=True,
        )


class IMeasureUnits(form.Schema):
    """Modifiers for computed value: units, multiplier, rounding rules"""
    
    form.widget(value_type=RadioFieldWidget)
    value_type = schema.Choice(
        title=u'Kind of value',
        description=u'What are the basic units of measure?',
        vocabulary=VALUE_TYPE_CHOICES,
        required=True,
        )

    multiplier = schema.Float(
        title=u'Value multiplier constant',
        description=u'What constant numeric (whole or decimal number) '\
                    u'should the raw computed value be multiplied by?  For '\
                    u'percentages computed with both a numerator and '\
                    u'denominator, enter 100.',
        default=1.0,
        )

    units = schema.TextLine(
        title=u'Units of measure',
        description=u'Label for units of measure (optional).',
        required=False,
        )

    form.widget(rounding=RadioFieldWidget)
    rounding = schema.Choice(
        title=u'(optional) Rounding rule',
        description=u'You may choose to round decimal values to integer '\
                    u'(whole or negative non-decimal number) values using '\
                    u'a rounding rule; be default, no rounding takes place.',
        vocabulary=ROUNDING_CHOICES,
        required=False,
        default='',
        )

    display_precision = schema.Int(
        title=u'Display precision',
        description=u'When displaying a decimal value, how many places '\
                    u'beyond the decimal point should be displayed in '\
                    u'output?  Default: two digits after the decimal point.',
        default=2,
        )


## content type interfaces:

class IMeasureDefinition(form.Schema,
                         IAttributeUUID,
                         IMeasureNaming,
                         IMeasureCalculation,
                         IMeasureUnits):
    """
    Measure definition content interface.
    
    Note: measures get their bound form definition and data source
    type from the measure group containing them.
    
    There is a pretty safe assumption that a measure value should
    be a floating point number.
    """
    
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


class IMeasureGroup(form.Schema,
                    IAttributeUUID,
                    IMeasureFormDefinition,
                    IMeasureSourceType,
                    ):
    """
    Measure group (folderish) content interface.  Measure groups
    contain both measure and common topic/collection/dataset items
    used by all measures contained within.
    """


class IMeasureLibrary(IOrderedContainer, form.Schema, IAttributeUUID):
    """ 
    Marker interface for library folder containing measure groups, which
    contain measure definitions (and topic/collections as data sets).
    """


## adapter interfaces

class IMultiRecordMeasureFactory(Interface):
    """Adapter interface for content creation"""
    
    def __call__(data):
        """Create measures based on wizard data, see wizard.py"""

