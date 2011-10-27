from plone.directives import form, dexterity
from plone.formwidget.contenttree import UUIDSourceBinder
from plone.formwidget.contenttree.source import CustomFilter
from plone.formwidget.contenttree import ContentTreeFieldWidget
from plone.formwidget.contenttree import MultiContentTreeFieldWidget
from plone.uuid.interfaces import IUUID, IAttributeUUID
from zope.app.container.interfaces import IOrderedContainer
from zope.interface import Interface, invariant
from zope.interface.interfaces import IInterface
from zope.location.interfaces import ILocation
from zope import schema
from Acquisition import aq_inner

from uu.dynamicschema.interfaces import ISchemaSignedEntity
from uu.record.interfaces import IRecordContainer

from uu.formlibrary import _


# portal type constants:
DEFINITION_TYPE = 'uu.formlibrary.definition' #form definition portal_type
LIBRARY_TYPE = 'uu.formlibrary.library'
SIMPLE_FORM_TYPE = 'uu.formlibrary.simpleform'
MULTI_FORM_TYPE = 'uu.formlibrary.multiform'
FORM_SET_TYPE = 'uu.formlibrary.setspecifier'
FORM_TYPES = (MULTI_FORM_TYPE, SIMPLE_FORM_TYPE)


class BoundFormSourceBinder(UUIDSourceBinder):
    """
    A UUID source binder for use by a IFormQuery object searching for
    forms related to a definition.  The assumption behind this binder
    is that the form must have a definition (uuid) matching 
    IUUID(context.__parent__) -- such a search is carried out in the 
    catalog (pass UUIDSourceBinder constructor a kwarg with query) via
    a 'definition' index added by this package.
    """
    
    def __init__(self, navigation_tree_query=None, **kw):
        super(BoundFormSourceBinder, self).__init__(
            navigation_tree_query,
            portal_type=FORM_TYPES,
            **kw)
    
    def __call__(self, context):
        definition_uid = IUUID(aq_inner(context).__parent__)
        if definition_uid is None:
            return super(BoundFormSourceBinder, self).__call__(context)
        filter = self.selectable_filter.criteria.copy()
        filter.update({'definition': definition_uid})
        filter = CustomFilter(**filter)
        return self.path_source(
            self._find_page_context(context),
            selectable_filter=filter,
            navigation_tree_query=self.navigation_tree_query)


class IFormLibraryProductLayer(Interface):
    """Marker for form library product layer"""


class ISchemaProvider(Interface):
    """
    Object that provides a gettable (but not settable) attribute/property
    self.schema providing an interface object with zope.schema fields.
    """
    
    schema = schema.Object(
        title=_(u'Form schema'),
        description=_(u'Form schema; may be dynamically loaded from '\
                      u'serialization.'),
        schema=IInterface,
        required=True, #implementations should provide empty default
        readonly=True, #read-only property, though object returned is mutable
        )


class IFormDefinition(form.Schema, ISchemaProvider, IOrderedContainer,
                      IAttributeUUID):
    """
    Item within a form library that defines a specific form for
    use across multiple form instances in a site.  The form 
    definition manages itself as a schema context for use by 
    plone.schemaeditor, and may contain as a folder other types of
    configuration items. 
    """
    
    title = schema.TextLine(
        title=u'Title',
        description=u'Name of form definition; used to create an identifier.',
        required=True,
        )
    
    description = schema.Text(
        title=u'Description',
        description=u'Optional description of this form definition.',
        required=False,
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


class IFormQuery(form.Schema, ILocation, IAttributeUUID):
    """
    Query specification for filtering a set of forms.  self.__parent__
    (from ILocation interface) is always expected to be an object
    providing IFormDefinition.
    """
    
    form.omitted('__name__') # not for editing

    form.fieldset(
        'formsearch',
        label=u"Form search",
        fields=[
            'query_title',
            'query_subject',
            'query_state',
            'query_start',
            'query_end',
            ]
        )
    
    form.fieldset(
        'formselect',
        label=u"Form selection",
        fields=[
            'target_uids',
            ]
        )
    
    title = schema.TextLine(
        title=u'Title',
        description=u'Name of form set.',
        required=True,
        )
    
    description = schema.Text(
        title=u'Description',
        description=u'Description of the form set resulting from '\
                    u'selection or query.',
        required=False,
        )
    
    query_title = schema.TextLine(
        title=u'Title',
        description=u'Full text search of title of forms.',
        required=False,
        )
    
    query_subject = schema.List(
        title=u'Tags',
        description=u'Query for any forms matching tags or subject.',
        value_type=schema.TextLine(),
        required=False,
        defaultFactory=list, #req zope.schema >= 3.8.0
        )
    
    query_state = schema.List(
        title=u'Workflow state(s)',
        description=u'List of workflow states.',
        value_type=schema.Choice(
            vocabulary=u'plone.app.vocabularies.WorkflowStates', #named vocab
            ),
        defaultFactory=list, #req zope.schema >= 3.8.0
        )
    
    query_start = schema.Date(
        title=u'Date range start',
        description=u'Date range inclusion query (start).',
        required=False,
        )
    
    query_end = schema.Date(
        title=u'Date range end',
        description=u'Date range inclusion query (end).',
        required=False,
        )
    
    form.widget(target_uids=MultiContentTreeFieldWidget)
    target_uids = schema.List(
        title=u'Select form instances',
        description=u'Select form instances',
        value_type=schema.Choice(
            source=BoundFormSourceBinder(),
            ),
        defaultFactory=list, #req zope.schema >= 3.8.0
        )
    
    def __iter__(self):
        """
        Return iterator over item (key/value) tuples such that
        an object providing IFormQuery can be cast to a dict or
        other mapping type.  The purpose of casing a query to
        a mapping is for use in a search engine / catalog / indexing
        system expecting such.
        """


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
        description=u'Underlying set elements as a Python set object ' \
                    u'containing string UUID representations.',
        defaultFactory=set, # req zope.schema >= 3.8.0
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
        fields=['notes',]
        )   
    
    title = schema.TextLine(
        title=_(u'Title'),
        description=_(u'Title for audit form instance; usually name of '\
                      u'a calendar period.'),
        required=True,
        )   
    
    start = schema.Date(
        title=_(u'Start date'),
        description=_(u'Start date for reporting period.'),
        required=False,
        )   
    
    end = schema.Date(
        title=_(u'End date'),
        description=_(u'End date for reporting period.'),
        required=False,
        )   
    
    process_changes = schema.Text(
        title=_(u'Process changes'),
        description=_(u'Notes about changes in goals, process, '\
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
        description=u'Choose a form definition, schema bound to this form.',
        source=UUIDSourceBinder(portal_type=DEFINITION_TYPE),
        )


class ISimpleForm(IBaseForm):
    """
    Simple form is a content item that provides one form entry record
    providing IFormEntry.
    """
    
    form.omitted('data')
    data = schema.Object(
        title=u'Form record data',
        schema=IFormEntry,
        required=False,
        )


class IMultiForm(form.Schema, IRecordContainer, ISchemaProvider):
    """
    A multi-form is a content item that provides 0..* form entry records
    providing IFormEntry via an IRecordContainer inteface, identifying
    record values by a record UUID (key).
    """

