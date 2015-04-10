from datetime import datetime

from persistent.dict import PersistentDict
from persistent.list import PersistentList
from plone.app.textfield import RichText
from plone.directives import form, dexterity
from plone.formwidget.contenttree import UUIDSourceBinder
from plone.formwidget.contenttree import ContentTreeFieldWidget
from plone.formwidget.contenttree import MultiContentTreeFieldWidget
from plone.uuid.interfaces import IAttributeUUID
from z3c.form.browser.textarea import TextAreaFieldWidget
from zope.container.interfaces import IOrderedContainer
from zope.interface import Interface, Invalid, invariant
from zope.interface.interfaces import IInterface
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from zope import schema

try:
    import z3c.blobfile  # noqa
    from plone.namedfile.field import NamedBlobImage as NamedImage
except:
    from plone.namedfile.field import NamedImage  # no z3c.blobfile support

from uu.dynamicschema.interfaces import ISchemaSignedEntity
from uu.dynamicschema.interfaces import DEFAULT_MODEL_XML, DEFAULT_SIGNATURE
from uu.dynamicschema.interfaces import valid_xml_schema
from uu.record.interfaces import IRecordContainer
from uu.retrieval.interfaces import ISimpleCatalog
from uu.smartdate.browser.widget import SmartdateFieldWidget

from uu.formlibrary import _
from uu.formlibrary.utils import DOW


# portal type constants:
DEFINITION_TYPE = 'uu.formlibrary.definition'  # form definition portal_type
LIBRARY_TYPE = 'uu.formlibrary.library'
SIMPLE_FORM_TYPE = 'uu.formlibrary.simpleform'
MULTI_FORM_TYPE = 'uu.formlibrary.multiform'
FORM_SET_TYPE = 'uu.formlibrary.setspecifier'
FIELD_GROUP_TYPE = 'uu.formlibrary.fieldgroup'
SERIES_TYPE = 'uu.formlibrary.series'
FILTER_TYPE = 'uu.formlibrary.recordfilter'
COMPOSITE_FILTER_TYPE = 'uu.formlibrary.compositefilter'
FORM_TYPE_NAMES = {
    MULTI_FORM_TYPE: u'Multi-record form',
    SIMPLE_FORM_TYPE: u'Flex form',
    }
FORM_TYPES = tuple(FORM_TYPE_NAMES.keys())


mkterm = lambda token, title: SimpleTerm(token, title=title)
_mkvocab = lambda s: SimpleVocabulary([mkterm(t, title) for (t, title) in s])
_terms = lambda s: SimpleVocabulary([SimpleTerm(t) for t in s])
mkvocab = lambda s: _mkvocab(s) if s and isinstance(s[0], tuple) else _terms(s)


class IFormLibraryProductLayer(Interface):
    """Marker for form library product layer"""


class ISchemaProvider(Interface):
    """
    Object that provides a gettable (but not settable) attribute/property
    self.schema providing an interface object with zope.schema fields.
    """

    schema = schema.Object(
        title=_(u'Form schema'),
        description=_(u'Form schema; may be dynamically loaded from '
                      u'serialization.'),
        schema=IInterface,
        required=True,  # implementations should provide empty default
        readonly=True,  # r/o property, though object returned is mutable
        )


class IDefinitionBase(form.Schema, ISchemaProvider, IAttributeUUID):
    """Base for form, form-group definitions"""

    form.omitted('signature')  # instance attribute, not editable form field
    signature = schema.BytesLine(
        title=_(u'Schema signature'),
        description=_(u'MD5 hexidecimal digest hash of entry_schema XML.'),
        default=DEFAULT_SIGNATURE,
        required=False,
        )

    form.omitted('signature_history')  # attribute, not editable form field
    signature_history = schema.List(
        title=_(u'Signature history stack'),
        description=_(u'Chronologically-ordered list of MD5 hexidecimal '
                      u'digest hashes of entry_schema XML.'),
        value_type=schema.BytesLine(),
        defaultFactory=list,
        )

    title = schema.TextLine(
        title=u'Title',
        description=u'Name of definition; this is used as a label displayed '
                    u'when binding forms to this definition, and also is '
                    u'used to help create a unique short name for the '
                    u'definition used in its URL.',
        required=True,
        )

    description = schema.Text(
        title=u'Description',
        description=u'Optional description of this form definition.',
        required=False,
        )

    form.widget(entry_schema=TextAreaFieldWidget)
    entry_schema = schema.Bytes(
        title=_(u'Form schema XML'),
        description=_(u'Serialized form schema XML.'),
        constraint=valid_xml_schema,
        default=DEFAULT_MODEL_XML,
        required=False,
        )

    # NOTE: this field must be last in interface code: identifier collision
    form.omitted('schema')  # instance attribute, but not editable form field
    schema = schema.Object(
        title=_(u'Form schema'),
        description=_(u'Form schema based upon entry_schema XML, usually '
                      u'a reference to a transient interface object '
                      u'looked up from persistent attribute self.signature.'),
        schema=IInterface,
        required=True,  # implementations should provide empty default
        readonly=True,  # read-only property, though object returned is mutable
        )

    def schema_version(signature):
        """
        Return the integer index of the signature in self.signature_history
        plus one (version numbers are one-indexed, not zero-indexed).  If
        signature passed is not found in history, return -1.
        """


class IDefinitionHistory(Interface):
    """
    Metadata about any changes to a form definition or its contents.
    Effectively a singular log entry; if multiple edits happen in
    one transaction, they should have distinct IDefinitionHistory
    objects in a log or list of history.
    """

    namespace = schema.BytesLine(
        title=u'Namespace',
        description=u'ID or path of modified object relative to definition.',
        default='',  # empty string is path to definition itself.
        )

    signature = schema.BytesLine(
        title=u'Schema signature',
        description=u'Schema signature at modification time, if applicable.',
        required=False,
        )

    modified = schema.Datetime(
        title=u'Modification time',
        description=u'Date/time stamp (datetime object) of modification.',
        defaultFactory=datetime.now,  # requires zope.schema >= 3.8.0
        )

    modification = schema.Choice(
        title=u'Modification type',
        vocabulary=mkvocab((
            ('modified', u'Definition modified'),
            ('schema', u'Definition (primary) schema modified'),
            ('group-added', u'Field group added'),
            ('group-modified', u'Field group definition modified'),
            ('group-deleted', u'Field group deleted'),
            ('group-schema', u'Field group schema modified'),
            ('formset-added', u'Form set added'),
            ('formset-modified', u'Form set modified'),
            ('formset-deleted', u'Form set deleted'),
            )),
        default='modified',
        )

    note = schema.Text(
        title=u'Note',
        description=u'Note or log message about modification.',
        required=False,
        )


class IFormDefinition(IDefinitionBase, IOrderedContainer):
    """
    Item within a form library that defines a specific form for
    use across multiple form instances in a site.  The form
    definition manages itself as a schema context for use by
    plone.schemaeditor, and may contain as a folder other types of
    configuration items.
    """

    form.fieldset(
        'Configuration',
        label=u"Form configuration",
        fields=[
            'form_css',
            'entry_schema',
            'sync_states',
            'metadata_definition',
            ]
        )

    form.fieldset(
        'Display',
        label=u"Form display metadata",
        fields=[
            'multiform_display_mode',
            'multiform_entry_mode',
            'stacked_columns',
            'instructions',
            'logo',
            ]
        )

    form.widget(form_css=TextAreaFieldWidget)
    form_css = schema.Bytes(
        title=_(u'Form styles'),
        description=_(u'CSS stylesheet rules for form (optional).'),
        required=False,
        )

    sync_states = schema.List(
        title=u'Auto-sync workflow states',
        description=u'Workflow states for form instances to automatically '
                    u'sync changes to; instances in other states will '
                    u'retain schema of previous definition revisions',
        value_type=schema.Choice(
            vocabulary='plone.app.vocabularies.WorkflowStates'),
        defaultFactory=lambda: list(('visible',)),
        )

    multiform_display_mode = schema.Choice(
        title=_(u'Multi-record form display mode?'),
        description=_(u'Read-only display layout, applies only to '
                      u'multi-record forms.'),
        vocabulary=mkvocab((
            'Columns',
            'Stacked',
            )),
        default='Stacked',
        )

    multiform_entry_mode = schema.Choice(
        title=_(u'Multi-record form entry mode?'),
        description=_(u'Form entry display layout, applies only to '
                      u'multi-record forms.'),
        vocabulary=mkvocab((
            'Columns',
            'Stacked',
            )),
        default='Stacked',
        )

    stacked_columns = schema.Choice(
        title=_(u'Column count (stacked)'),
        description=u'When using stacked boxes entry/display mode, how many '
                    u'colmns should be created in the layout?',
        vocabulary=mkvocab(tuple(range(1, 6))),
        default=3,
        )

    instructions = RichText(
        title=_(u'Instructions'),
        description=_(u'Instructions for data entry'),
        required=False,
        )

    logo = NamedImage(
        title=_(u'Logo'),
        description=_(u'Please upload a logo image for display on the form.'),
        required=False,
        )

    form.omitted('definition_history')
    definition_history = schema.List(
        title=u'Definition history',
        description=u'Modificaton history metadata log: chronological '
                    u'log of objects providing IDefinitionHistory '
                    u'metadata for form definition.',
        value_type=schema.Object(schema=IDefinitionHistory),
        defaultFactory=PersistentList,  # req. zope.schema >= 3.8.0
        )

    form.widget(metadata_definition=ContentTreeFieldWidget)
    metadata_definition = schema.Choice(
        title=u'Metadata definition',
        description=u'Select a form definition to provide metadata fields '
                    u'for this form (optional).',
        required=False,
        source=UUIDSourceBinder(portal_type=DEFINITION_TYPE),
        )

    def log(*args, **kwargs):
        """
        Given either a single argument of an IDefintionHistory object
        or keyword arguments related to its attributes, use/construct
        a history entry providing IDefinitionHistory, and store it
        in self.definition_history by append.
        """


class IFieldGroup(IDefinitionBase):
    """
    Group of fields within a form, provides its own schema distinct
    from the schema of the containing form definition.

    Depending upon group_usage, intended use of this group may be
    either in a fieldset-like capacity, or as a schema provider for
    a grid field (nested in a fieldset-like setup).
    """

    form.fieldset(
        'Configuration',
        label=u"Form configuration",
        fields=[
            'entry_schema',
            ]
        )

    form.omitted('id')  # generated from title, not edited generally
    id = schema.BytesLine()

    title = schema.TextLine(
        title=u'Title',
        description=u'Name of field group; used as a label displayed '
                    u'in group headings in form display/entry, and also is '
                    u'used to help create a unique short name for the '
                    u'group used in its URL.',
        required=True,
        )

    group_usage = schema.Choice(
        title=u'Field group usage',
        description=u'What type of use is expected for this field group?',
        vocabulary=SimpleVocabulary(
            [
                SimpleTerm(value=u'group', title=u'Single-record group'),
                SimpleTerm(value=u'grid', title=u'Multi-record grid'),
            ],
            ),
        default=u'group',
        )


class IFormComponents(Interface):
    """
    Adapter interface for an object providing access to the respective
    components making up the form definition:

      * An ordered tuple of names of fieldsets made up from the
        definition itself and field groups contained.

      * An (unordered) mapping / dict of name to group (IFieldGroup
        or IFieldDefinition -- anything providing either) values.

    Titles and schema for the groups should be obtained by calling
    code using this adapter, and are not provided by the adapter
    interface itself.  This also means the responsibility to wrap
    field group schema declared as a grid aslo is ommitted from the
    scope of this adapter.
    """

    names = schema.Tuple(
        title=u'Fieldset names',
        value_type=schema.BytesLine(),
        defaultFactory=list,  # req zope.schema > 3.8.0
        readonly=True,  # read-only property
        )

    groups = schema.Dict(
        title=u'Fieldset groups',
        key_type=schema.BytesLine(),
        value_type=schema.Object(schema=IDefinitionBase),
        defaultFactory=dict,  # req zope.schema > 3.8.0
        readonly=True,  # read-only dict, though groups are mutable
        )


class IFormLibrary(form.Schema, IOrderedContainer, IAttributeUUID):
    """
    Container/folder interface for library of form definitions.
    Keys are ids, values provided IFormDefinition.
    """

    title = schema.TextLine(
        title=u'Title',
        description=u'Name of form library; used to create its identifier.',
        required=True,
        )

    description = schema.Text(
        title=u'Description',
        description=u'Optional description of this form library.',
        required=False,
        )


class IFormEntry(ISchemaSignedEntity):
    """
    Lightweight (non-content) record containing form data
    for a single record, bound to a schema via md5 signature of
    the schema's serialization (provided via uu.dynamicschema).
    """


class IFormQuery(form.Schema):
    """
    Query specification for filtering a set of forms.
    """

    form.fieldset(
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
    form.widget(locations=MultiContentTreeFieldWidget)
    locations = schema.List(
        title=u'Included locations',
        description=u'Select locations (specific forms or containing '
                    u'folders, including form series and/or parent '
                    u'folders) to include.  If you do not choose at '
                    u'least one location, all forms will be included and '
                    u'optionally filtered. If you choose locations, only '
                    u'forms within those locations will be included and '
                    u'optionally filtered by any chosen filter criteria.',
        value_type=schema.Choice(
            source=UUIDSourceBinder(),
            ),
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
        description=u'Query for any forms matching tags or subject.',
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

    form.widget(query_start=SmartdateFieldWidget)
    query_start = schema.Date(
        title=u'Filter: date range start',
        description=u'Date range inclusion query (start).',
        required=False,
        )

    form.widget(query_end=SmartdateFieldWidget)
    query_end = schema.Date(
        title=u'Filter: date range end',
        description=u'Date range inclusion query (end).',
        required=False,
        )

    def brains(self):
        """Return an iterable of catalog brains for forms included."""

    def forms(self):
        """Return an iterable of form objects included."""


class IFormSet(Interface):
    """
    An immutable set of UUIDs and an immutable iterable mapping of
    UUID keys to form objects.

    This component type is usually transient, adapting some context
    (usually an object providing IFormDefinition).  The exact
    membership of the contained/wrapped set (self.contents) is
    usually the result of a query relative to the adapted context.

    This component provides a limited subset of Python set
    type/interface functionality (documented immutable set operations).

    For set arithmetic operations, if 'other' passed is a base Python
    set, not an object providing IFormSet, the result of any operation
    returning a set should be to return an item of the same type as
    self.

    For set comparison operations, if the 'other' passed is a base
    Python set, not providing IFormSet, comparisons should be based
    upon ONLY membership of UUID contents, not the type of the other.

    Though the underlying self.contents should be a mutable set, this
    exterior wrapper interface is non-mutable, acting more like a
    frozenset (implementing the common operations of set/frozenset).
    To modify the underlying set, use operations on self.contents.
    Modification of self.contents immediately affects all aspects
    of this set wrapper (state and behavior as immutable set and as
    an immutable iterable mapping).
    """

    name = schema.TextLine(
        title=u'Set name',
        description=u'Name of set (if named) or None.',
        required=False,
        default=None,
        )

    contents = schema.Set(
        title=u'Set elements',
        description=u'Underlying set elements as a Python set object '
                    u'containing string UUID representations.',
        defaultFactory=set,  # req zope.schema >= 3.8.0
        )

    def __len__():
        """Return number of elements (form UUIDs in set)."""

    def __iter__():
        """Return iterable over self.contents (UUID values)"""

    def __contains__(value):
        """
        Passed a value of either UUID or IBaseForm instance, is the UUID
        of the form in self.contents.
        """

    # read-only / immutable iterable mapping interface methods:

    def __getitem__(key):
        """
        Given a UID key, get form object value; raise KeyError on a key
        not in self.keys() or a value that cannot be located.
        """

    def get(key, default=None):
        """
        Given a UID key, get and return form object, or return default.
        """

    def keys():
        """Return list of UUID keys"""

    def values():
        """Return list of form object values"""

    def items():
        """Return list of (UUID, form) tuples"""

    def iterkeys():
        """Return iterator over keys"""

    def itervalues():
        """Return iterator over values"""

    def iteritems():
        """Return iterator over items"""

    # set interface methods:

    def __and__(other):
        """
        Return set intersection of self and other as object providing
        IFormSet.
        """

    def intersection(other):
        """Alternate spelling for __and__(other)"""

    def __or__(other):
        """
        Return set union of self and other as object providing IFormSet.
        """

    def union(other):
        """Alternate spelling for __or__(other)"""

    def __xor__(other):
        """
        Return the symetric difference of self and other (items in
        one or the other, but not both).
        """

    def symetric_difference(other):
        """Alternate spelling for __xor__(other)"""

    def __sub__(other):
        """Relative complement or difference self - other"""

    def difference(other):
        """Alternate spelling for __sub__(other)"""

    def __eq__(other):
        """
        Is self, other equivalent set by element membership.
        """

    def __ne__(other):
        """
        Is self, other non-equivalent by element membership.
        """

    def __gt__(other):
        """
        Is self a "true" superset of other such that self != other.
        """

    def __ge__(other):
        """
        Is self a superset of other or has identical set membership.
        """

    def __lt__(other):
        """
        Is self a "true" subset of other such that self != other.
        """

    def __le__(other):
        """
        Is self a subset of other or has identical set membership.
        """

    def issuperset(other):
        """Alternate spelling for self.__ge__(other)"""

    def issubset(other):
        """Alternate spelling for self.__le__(other)"""

    def isdisjoint(other):
        """
        Return False if self and other contain any element UUIDs
        that are identical, otherwise return True that self and others
        are disjoint sets respective to each other.
        """

    def copy():
        """Create a copy of this set wrapper and contained set"""


class IPeriodicFormInstance(form.Schema, IAttributeUUID):
    """Base form instance interface"""

    form.fieldset(
        'Review',
        label=u"Review information",
        fields=['notes']
        )

    title = schema.TextLine(
        title=_(u'Title'),
        description=_(u'Title for form instance; usually contains the '
                      u'name of a calendar period.'),
        required=True,
        )

    form.widget(start=SmartdateFieldWidget)
    start = schema.Date(
        title=_(u'Start date'),
        description=_(u'Start date for reporting period.'),
        required=False,
        )

    form.widget(end=SmartdateFieldWidget)
    end = schema.Date(
        title=_(u'End date'),
        description=_(u'End date for reporting period.'),
        required=False,
        )

    process_changes = schema.Text(
        title=_(u'Process changes'),
        description=_(u'Notes about changes in goals, process, '
                      u'expectations for period of form.'),
        required=False,
        )

    dexterity.read_permission(notes='cmf.ReviewPortalContent')
    dexterity.write_permission(notes='cmf.ReviewPortalContent')
    notes = schema.Text(
        title=_(u'Notes'),
        description=_(u'Administrative, review notes about form instance.'),
        required=False,
        )

    @invariant
    def validate_start_end(obj):
        if not (obj.start is None or obj.end is None) and obj.start > obj.end:
            raise Invalid(_(u"Start date cannot be after end date."))


class IBaseForm(form.Schema, ISchemaProvider, IPeriodicFormInstance):
    """
    Base form interface: form instances are bound to a definition which
    provides the basis for how self.schema is provided.
    """

    form.widget(definition=ContentTreeFieldWidget)
    definition = schema.Choice(
        title=u'Bound form definition',
        description=u'Select a form definition to bind to this form. '
                    u'The definition that you choose will control the '
                    u'available fields and behavior of this form instance.',
        source=UUIDSourceBinder(portal_type=DEFINITION_TYPE),
        )


class ISimpleForm(IBaseForm):
    """
    Simple form is a content item that provides one form entry record
    providing IFormEntry.
    """

    form.omitted('data')
    data = schema.Dict(
        title=u'Data mapping',
        description=u'Map data from fieldset name to record.',
        key_type=schema.BytesLine(title=u'Fieldset name'),
        value_type=schema.Object(schema=IFormEntry),
        defaultFactory=PersistentDict,  # requires zope.schema >= 3.8.0
        )


class IMultiForm(IBaseForm, IRecordContainer, ISchemaProvider):
    """
    A multi-form is a content item that provides 0..* form entry records
    providing IFormEntry via an IRecordContainer inteface, identifying
    record values by a record UUID (key).
    """

    # omit IRecordContainer['factory'] from generated form
    form.omitted('factory')

    form.omitted('catalog')
    catalog = schema.Object(
        title=u'Catalog',
        description=u'Catalog indexes multi-record form data',
        schema=ISimpleCatalog,
        required=False,  # may initially be None
        )

    entry_notes = schema.Text(
        title=_(u'Entry notes'),
        description=_(u'Any notes about form entries for this period.'),
        required=False,
        )


class IPeriodicSeries(form.Schema):
    """Definition of a sequence of periods of time"""

    frequency = schema.Choice(
        title=_(u'Frequency'),
        description=_(u'Frequency of form collection.'),
        vocabulary=mkvocab((
            'Monthly',
            'Quarterly',
            'Weekly',
            'Annual',
            'Twice monthly',
            'Every two months',
            'Every other month',
            'Every six months',
            'Daily',
            )),
        default='Monthly',
        )

    form.widget(start=SmartdateFieldWidget)
    start = schema.Date(
        title=_(u'Start date'),
        description=_(u'Start date for series.'),
        required=False,
        )

    form.widget(end=SmartdateFieldWidget)
    end = schema.Date(
        title=_(u'End date'),
        description=_(u'End date for series.'),
        required=False,
        )

    active_weekdays = schema.List(
        title=_(u'Active weekdays'),
        description=_(u'Working or active days of week; the first and last '
                      u'of which are considered when computing reporting '
                      u'periods for populating forms of weekly frequency '
                      u'(safely ignored for any non-weekly frequencies). '
                      u'Please note: days of week must be in sequential '
                      u'order.'),
        value_type=schema.Choice(
            vocabulary=mkvocab((
                'Monday',
                'Tuesday',
                'Wednesday',
                'Thursday',
                'Friday',
                'Saturday',
                'Sunday',
                )),
            ),
        constraint=DOW.validate,     # any seven days must be in sequence!
        defaultFactory=DOW.weekdays,  # requires zope.schema >= 3.8.0
        required=False,
        )


class IFormSeries(form.Schema, IPeriodicSeries):
    """
    A time-series container of related periodic forms, may contain
    shared metadata about that group of forms.
    """

    form.fieldset(
        'Display',
        label=u"Form display metadata",
        fields=['contact', 'logo', 'form_css']
        )

    form.fieldset(
        'Review',
        label=u"Review information",
        fields=['notes']
        )

    title = schema.TextLine(
        title=_(u'Title'),
        description=_(u'Series title or heading; displayed on forms.'),
        required=True,
        )

    subhead = schema.TextLine(
        title=_(u'Sub-heading'),
        description=_(u'Second-level title/heading for form display.'),
        required=False,
        )

    description = schema.Text(
        title=u'Description',
        description=_(u'Series description; may be displayed on forms.'),
        required=False,
        )

    contact = RichText(
        title=_(u'Contact'),
        description=_(u'Project manager or coordinator contact information.'),
        required=False,
        )

    series_info = RichText(
        title=_(u'Series info'),
        description=_(
            u'Series information for display on series summary page.'
            ),
        required=False,
        )

    logo = NamedImage(
        title=_(u'Logo'),
        description=_(u'Optionally upload a logo image for display on the '
                      u'form.  If present, overrides any logo from form '
                      u'definitions on the display of contained forms'),
        required=False,
        )

    form.widget(form_css=TextAreaFieldWidget)
    form_css = schema.Bytes(
        title=_(u'Form styles'),
        description=_(u'Additional CSS stylesheet rules for forms contained '
                      u'within this series (optional).'),
        required=False,
        )

    dexterity.read_permission(notes='cmf.ReviewPortalContent')
    dexterity.write_permission(notes='cmf.ReviewPortalContent')
    notes = schema.Text(
        title=_(u'Notes'),
        description=_(u'Administrative, review notes about series.'),
        required=False,
        )

    form.order_after(frequency='description')
    form.order_after(start='frequency')
    form.order_after(end='start')
    form.order_after(active_weekdays='end')

    @invariant
    def validate_start_end(obj):
        if not (obj.start is None or obj.end is None) and obj.start > obj.end:
            raise Invalid(_(u"Start date cannot be after end date."))


class IPopulateForms(form.Schema):
    """Interface/schema for wizard form view for populating forms"""

    form_type = schema.Choice(
        title=_(u'Form type'),
        description=_(u'Select a type of form to populate.'),
        vocabulary=mkvocab(FORM_TYPE_NAMES.items()),
        default=SIMPLE_FORM_TYPE,
        )

    form.widget(definition=ContentTreeFieldWidget)
    definition = schema.Choice(
        title=u'Choose form definition',
        description=u'Select a form definition to bind to these created '
                    u'forms.',
        source=UUIDSourceBinder(portal_type=DEFINITION_TYPE),
        required=True,
        )

    title_prefixes = schema.List(
        title=_(u'Title prefixes'),
        description=_(u'Optional text to be placed at front of title; if '
                      u'present title components are separated by hyphen. '
                      u'One prefix per-line may be used.'),
        value_type=schema.TextLine(),
        required=False,
        defaultFactory=list,
        )

    title_suffixes = schema.List(
        title=_(u'Title suffixes'),
        description=_(u'Optional text to be placed at end of title; if '
                      u'present title components are separated by hyphen. '
                      u'One suffix per-line may be used.'),
        value_type=schema.TextLine(),
        required=False,
        defaultFactory=list,
        )

    custom_range = schema.Bool(
        title=_(u'Use custom ranges?'),
        description=_(u'Use custom start/end dates and frequency, instead '
                      u'of relying upon metadata on this form series?'),
        default=False,
        )


class ICSVColumn(Interface):
    """
    Abstraction for a CSV column specification used for a set of records.
    """

    name = schema.BytesLine(
        title=u'Field column name',
        description=u'Column name, based on field name',
        required=True,
        )

    title = schema.TextLine(
        title=u'Title',
        description=u'Column / field title',
        default=u'',
        required=False,
        )

    field = schema.Object(
        title=u'Field object',
        description=u'Field object from interface',
        schema=Interface,
        )

    def get(record):
        """Return column value as string for a record or an empty string."""


class IMultiFormCSV(Interface):
    """Adapter interface to get CSV from a multiple-form context"""


