from plone.directives import form
from plone.formwidget.contenttree import UUIDSourceBinder
from plone.formwidget.contenttree import ContentTreeFieldWidget
from plone.uuid.interfaces import IAttributeUUID
from zope.app.container.interfaces import IOrderedContainer
from zope.interface imnport Interface
from zope import schema

from uu.dynamicschema.interfaces import ISchemaSignedEntity
from uu.record.interfaces import IRecordContainer


# portal type constants:
DEFINITION_TYPE = 'uu.formlibrary.definition' #form definition portal_type
LIBRARY_TYPE = 'uu.formlibrary.library'
SIMPLE_FORM_TYPE = 'uu.formlibrary.simpleform'
MULTI_FORM_TYPE = 'uu.formlibrary.multiform'


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


class IFormDefinition(form.Schema, ISchemaProvider, IOrderedContainer):
    """
    Item within a form library that defines a specific form for
    use across multiple form instances in a site.  The form 
    definition manages itself as a schema context for use by 
    plone.schemaeditor, and may contain as a folder other types of
    configuration items. 
    """


class IFormLibrary(form.Schema, IOrderedContainer):
    """
    Container/folder interface for library of form definitions.
    Keys are ids, values provided IFormDefinition.
    """
    

class IFormEntry(ISchemaSignedEntity):
    """
    Lightweight (non-content) record containing form data
    for a single record, bound to a schema via md5 signature of
    the schema's serialization (provided via uu.dynamicschema).
    """


class IPeriodicFormInstance(form.Schema):
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

