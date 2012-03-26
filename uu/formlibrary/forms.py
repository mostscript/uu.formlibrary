from datetime import datetime

import transaction
from persistent.dict import PersistentDict
from plone.dexterity.content import Item
from plone.autoform.form import AutoExtensibleForm
from plone.autoform.interfaces import WIDGETS_KEY
from plone.z3cform.fieldsets.group import GroupFactory
from z3c.form import form, field, button, converter, widget
from z3c.form.testing import TestRequest
from zope.app.component.hooks import getSite
from zope.component import adapter, queryUtility
from zope.event import notify
from zope.interface import implements, implementer
from zope.globalrequest import getRequest
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent import Attributes
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import IDate
from DateTime import DateTime
from Products.CMFPlone.utils import getToolByName

from uu.dynamicschema.schema import new_schema
from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE, DEFAULT_MODEL_XML
from uu.dynamicschema.interfaces import ISchemaSaver
from uu.record.base import RecordContainer
from uu.record.interfaces import IRecord
from uu.smartdate.converter import ColloquialDateConverter
from uu.smartdate.browser.widget import SmartdateFieldWidget
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IBaseForm, IFormDefinition
from uu.formlibrary.interfaces import IFormComponents
from uu.formlibrary.interfaces import ISchemaProvider
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.record import FormEntry
from uu.formlibrary.utils import grid_wrapper_schema
from uu.formlibrary.utils import WIDGET as GRID_WIDGET


# a widget object (ab)used for data converters from z3c.schema:
mkwidget = lambda request: widget.Widget(request)
TEXT_WIDGET = mkwidget(TestRequest())


def field_type(field):
    if hasattr(field, '_type'):
        spec = field._type
        if isinstance(spec, tuple):
            return spec[0]
        if spec:
            return spec
    return None #could not guess


flip = lambda s: (s[1], s[0])
invert = lambda s: map(flip, s)


def is_grid_wrapper_schema(schema):
    if 'data' in schema and WIDGETS_KEY in schema.getTaggedValueTags():
        widgets = schema.getTaggedValue(WIDGETS_KEY)
        if 'data' in widgets and widgets['data'] == GRID_WIDGET:
            return True
    return False

## form-related adapters:

@implementer(IFormDefinition)
@adapter(IBaseForm)
def form_definition(form):
    def_uid = form.definition
    if def_uid is None:
        raise ValueError('form lacks definition identifier')
    site = getSite()
    catalog = getToolByName(site, 'portal_catalog')
    r = catalog.search({'UID':def_uid, 'portal_type':DEFINITION_TYPE})
    if not r:
        raise ValueError('could not locate form definition')
    return r[0]._unrestrictedGetObject()


class ComposedForm(AutoExtensibleForm, form.Form):
    """
    A form composed from multiple schema adapting a form definition.
    This composition uses (base class from) plone.autoform to compose
    a merged form.
    """
    
    ignoreContext = True    # form operates without edit context.
    
    autoGroups = True       # autoGroups requires modification to plone.autoform
                            # to support anonymouse schema without __name__
                            # See commit on GitHub: http://goo.gl/3W233
    
    enable_form_tabbing = False; # do not display fieldsets in tabs.
    
    # schema must be property, not attribute for AutoExtensibleForm sublcass
    @property
    def schema(self):
        return self._schema
    
    @property
    def additionalSchemata(self):
        return self._additionalSchemata
    
    def __init__(self, context, request):
        """
        Construct composed form given (default) schema an a tuple
        of ordered additional schema key/value pairs of (string)
        component name keys to schema values.
        """
        self.context = context
        self.request = request
        # form definition will either be context, or adaptation of context.
        # see uu.formlibrary.forms.form_definition for adapter example.
        self.definition = IFormDefinition(self.context)
        self._schema = self.definition.schema
        self.groups = [] # modified by updateFieldsFromSchemata()
        
        self.components = IFormComponents(self.definition)
        self.group_schemas = self._group_schemas()
        self.group_titles = self._group_titles()

        # mapping: schema to names:
        self.schema_names = dict(invert(self.group_schemas))

        # ordered list of additional schema for AutoExtensibleForm:
        self._additionalSchemata = tuple(
            [t[1] for t in self.group_schemas if t[0]]
            )
        #super(ComposedForm, self).__init__(self, context, request)
        form.Form.__init__(self, context, request)
        self.saved = False #initial value: no duplication of save...
        self.save_attempt = False # flag for save attempt, success or not
    
    def _group_schemas(self):
        result = []
        for name in self.components.names:
            group = self.components.groups[name]
            schema = group.schema
            if group.group_usage == u'grid':
                schema = grid_wrapper_schema(schema)
            result.append( (name, schema) )
        return result

    def _group_titles(self):
        result = {}
        for name, group in self.components.groups.items():
            result[name] = group.Title()
        return result

    def updateFieldsFromSchemata(self):
        self.groups = []
        for name, schema in self.group_schemas:
            if name == '':
                continue # default, we don't need another group
            title = self.group_titles.get(name, name)
            fieldset_group = GroupFactory(name, field.Fields(), title)
            self.groups.append(fieldset_group)
        super(ComposedForm, self).updateFieldsFromSchemata()
   
    def updateWidgets(self):
        date_fields = [f for f in self.fields.values()
                        if IDate.providedBy(f.field)]
        for field in date_fields:
            field.widgetFactory = SmartdateFieldWidget
        for group in self.groups:
            date_fields = [f for f in group.fields.values()
                            if IDate.providedBy(f.field)]
            for field in date_fields:
                field.widgetFactory = SmartdateFieldWidget
        super(ComposedForm, self).updateWidgets()
    
    def datagridInitialise(self, subform, widget):
        if not hasattr(self, '_widgets_initialized'):
            self._widgets_initialized = [] # don't duplicate effort!
        if subform not in self._widgets_initialized:
            date_fields = [f for f in subform.fields.values()
                            if IDate.providedBy(f.field)]
            for formfield in date_fields:
                formfield.widgetFactory = SmartdateFieldWidget
        self._widgets_initialized.append(subform)
    
    def getPrefix(self, schema):
        if schema in self.schema_names:
            return self.schema_names[schema]
        # fall-back will not work for anoymous schema without names, but
        # it is the best we can assume to do here:
        return super(ComposedForm, self).getPrefix(schema)
    
    def _saveResult(self, result):
        schemas = dict(self.group_schemas)
        data = self.context.data
        for name, values in result.items():
            name = str(name)
            schema = schemas.get(name, self._schema) #schema or default group
            if schema:
                group_record = self.context.data.get(name, None)
                if group_record is None:
                    group_record = self.context.data[name] = FormEntry()
                group_record.sign(schema)
                for fieldname, value in values.items():
                    setattr(group_record, fieldname, value)
    
    @button.buttonAndHandler(u'Save', condition=lambda form: form.mode=='input')
    def handleSave(self, action):
        self.save_attempt = True
        data, errors = self.extractData()
        if errors or IFormDefinition.providedBy(self.context) or self.saved:
            return #just validate if errors, or if context if defn
        if not self.saved:
            result = {} # submitted data. k: group name; v: dict of name/value
            group_keys = []
            for group in self.groups:
                groupdata = {}
                form_group_data = group.extractData()[0]
                for name, field in group.fields.items():
                    group_keys.append(name)
                    fieldname = field.field.__name__
                    default = getattr(field.field, 'default', None)
                    groupdata[fieldname] = form_group_data.get(name, default)
                result[group.__name__] = groupdata
            # filter default fieldset values, ignoring group values from data dict:
            result[''] = dict([(k,v) for k,v in data.items()
                                if k not in group_keys])
            self._saveResult(result)
            self.context.setModificationDate(DateTime())  # modified==now
            self.saved = True
            transaction.get().note('Saved form data')


## content-type implementations for form instances:

class SimpleForm(Item):
    """
    Single-record form instance tied to a specific form definition and its
    schema.
    """
   
    portal_type = SIMPLE_FORM_TYPE

    implements(ISimpleForm)
    
    def __init__(self, id=None, *args, **kwargs):
        super(SimpleForm, self).__init__(id, *args, **kwargs)
        self.data = PersistentDict() # of FormEntry()
        self.data[''] = FormEntry()  # always has default/unnamed fieldset


class MultiForm(Item, RecordContainer):
    """
    Multi-record form instance tied to a specific form definition and its
    schema.  Acts as a record container.
   
    Usage:
    ------
    
    Context / pre-requisite: in order to deal with forms, we need a place
    where schemas are managed (and persisted); this is an ISchemaSaver 
    utility; normally, this is a local (persistent utility) part of a 
    site:

    >>> from zope.component import queryUtility, getSiteManager
    >>> from zope.app.component.hooks import getSite
    >>> portal = getSite() # (for testing: set up by plone.testing layer)
    >>> assert portal is not None
    >>> sm = getSiteManager(portal)
    >>> assert sm is not None
    >>> from uu.dynamicschema.interfaces import ISchemaSaver
    >>> saver = queryUtility(ISchemaSaver) 
    >>> assert saver is sm.queryUtility(ISchemaSaver)
    >>> assert saver is not None
    
    We need a multi-form object:
    
    >>> from uu.formlibrary.forms import MultiForm
    >>> multi_form = MultiForm()
    >>> from uu.formlibrary.interfaces import IBaseForm, IMultiForm
    >>> assert IMultiForm.providedBy(multi_form)
    >>> assert IBaseForm.providedBy(multi_form)
    
    Now, the form must be hooked up to a definition.  We need a definition
    fixture that actually lives on the site.  Note, this doctest is run with
    plone.testing layer injected into globals as 'layer' -- we will use this
    to invoke our common test fixture factory:

    >>> from plone.app.testing import TEST_USER_ID, setRoles
    >>> setRoles(portal, TEST_USER_ID, ['Manager'])
    >>> assert layer is not None  # plone.testing layered() does this for us
    >>> class MockSuite(object):
    ...     def assertTrue(self, exp):
    ...         assert bool(exp)
    ... 
    >>> mocksuite = MockSuite()
    >>> from uu.formlibrary.tests.fixtures import CreateContentFixtures
    >>> CreateContentFixtures(mocksuite, layer).create()
    >>> assert 'formlib' in portal.contentIds()
    >>> assert 'def' in portal['formlib'].contentIds()
    
    We will use a multi_form instance created by these fixtures -- one 
    that actually has a place in the content hierarchy (lives in portal
    root, for simplicity's sake -- see uu.formlibrary.tests.fixtures):
    
    >>> multi_form = portal['multi']
    >>> assert multi_form.definition is None  # fixture setup never set this
    >>> definition = portal['formlib']['def']
    >>> from plone.uuid.interfaces import IUUID
    >>> assert IUUID(multi_form)
    >>> assert IUUID(definition)

    Let's bind the form to the definition:
    
    >>> multi_form.definition = IUUID(definition)
    >>> assert multi_form.definition is not None
    >>> assert isinstance(multi_form.definition, str)  # is UUID stringified
    
    Now we can actually get the definition by adapting the form to 
    IFormDefinition:
    
    >>> from uu.formlibrary.interfaces import IFormDefinition
    >>> from Acquisition import aq_base
    >>> assert aq_base(IFormDefinition(multi_form)) is aq_base(definition)
   
    The definition lacks any interesting schema:
    
    >>> from uu.dynamicschema.interfaces import DEFAULT_MODEL_XML
    >>> from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE
    >>> from plone.supermodel import serializeSchema
    >>> assert definition.signature == DEFAULT_SIGNATURE
    >>> assert serializeSchema(definition.schema) == DEFAULT_MODEL_XML

    Let's create a mock interface for more interesting schema:
    
    >>> from zope.interface import Interface
    >>> from zope import schema
    >>> class IMonkey(Interface):
    ...     title = schema.TextLine(title=u'Name of monkey', required=True)
    ...     count = schema.Int(title=u'How many monkeys?', default=3)
    ... 
    >>> IMonkey.__name__ = None  # make more like usual anonymous interfaces
    >>> monkey_xml = serializeSchema(IMonkey).strip()
    
    Let's save this interface via its XML on the definition, and use 
    modified event to trigger persistence in Schema Saver:
    
    >>> definition.entry_schema = monkey_xml
    >>> from zope.lifecycleevent import ObjectModifiedEvent
    >>> from zope.event import notify
    >>> notify(ObjectModifiedEvent(definition))  # => schema load from xml
    >>> assert definition.signature != DEFAULT_SIGNATURE # new schema, sig
    >>> assert serializeSchema(definition.schema) == monkey_xml

    Now, since we bound multi_form.definition to the UUID of the definition
    that just had its schema re-loaded, we can see this indirectly on 
    the multi_form instance:
    
    >>> assert multi_form._definition_schema() is definition.schema
    >>> assert multi_form.schema is definition.schema

    Multi forms are record containers, and thus have length and 
    containment checks for records within:
    
    >>> assert len(multi_form) == 0
    >>> import uuid #keys for entries are stringified UUIDs
    >>> randomuid = str(uuid.uuid4())
    >>> assert randomuid not in multi_form
    >>> assert multi_form.get(randomuid, None) is None
    
    And (as record containers) they have keys/values/items like a mapping:
    
    >>> assert multi_form.keys() == ()
    >>> assert multi_form.values() == ()
    >>> assert multi_form.items() == () #of course, these are empty now.

    Before we add chart/row/record items, we need to create them; there are
    two possible ways to do this:

    >>> from uu.formlibrary.record import FormEntry
    >>> entry1 = FormEntry()
    >>> entry2 = multi_form.create()  # preferred means of construction

    Both factory mechanisms create an entry item with a record_uid attribute:

    >>> from uu.formlibrary.interfaces import IFormEntry
    >>> assert IFormEntry.providedBy(entry1)
    >>> assert IFormEntry.providedBy(entry2)
    >>> is_uuid = lambda u: isinstance(u, str) and len(u)==36
    >>> assert is_uuid(entry1.record_uid)
    >>> assert is_uuid(entry2.record_uid)

    And, these are RFC 4122 UUIDs, so even randomly generated 128-bit ids
    have near zero chance of collision:
    
    >>> assert entry1.record_uid != entry2.record_uid
    >>> assert entry2.record_uid != randomuid
    
    Now when we have a parent context with a schema, the created entries will
    be signed with the schema and provide it.
    
    >>> entry3 = multi_form.create()
    >>> assert definition.schema.providedBy(entry3)
    >>> assert definition.schema['count'].default == 3
    >>> assert entry3.count == 3 #default field value via __getattr__ proxy 
    
    MultiForm.create() is the preferred factory when processing form data.
    This is because it can take a mapping of keys/values, and copy each
    field name/value onto object attributes -- if and only if the name in
    question is in the field schema.
    
    >>> entry4 = multi_form.create(data={'record_uid':randomuid})
    >>> assert entry4.record_uid == randomuid
    >>> entry5 = multi_form.create(data={'count':5})
    >>> assert entry5.count == 5
    >>> entry6 = multi_form.create(data={'not_in_schema':True, 'count':2})
    >>> assert not hasattr(entry6, 'not_in_schema')
    >>> assert entry6.count == 2

    """
    
    # TODO: update docstring with tests copied from uu.qiforms.content.ChartAudit
    # with modifications...
   
    portal_type = MULTI_FORM_TYPE

    implements(IMultiForm, ISchemaProvider)
    
    def __init__(self, id=None, **kwargs):
        Item.__init__(self, id, **kwargs)
        RecordContainer.__init__(self, factory=FormEntry)
    
    def _definition(self):
        try:
            definition = IFormDefinition(self)  # get definition
        except ValueError:
            return None
        return definition
    
    def _saver(self):
        """get schema saver component, possibly cache lookup"""
        return queryUtility(ISchemaSaver)
    
    def _definition_schema(self):
        """Get schema from form definition"""
        defn = self._definition()
        if defn is None:
            return self._saver().load(DEFAULT_MODEL_XML)
        return defn.schema
    
    def _definition_signature(self):
        """Get signature of schema from form definition"""
        defn = self._definition()
        if defn is None:
            return DEFAULT_SIGNATURE
        return defn.signature
    
    def __len__(self):
        return RecordContainer.__len__(self)
    
    def __getattr__(self, name):
        """In lieu of using Pyton property for self.schema"""
        if name == 'schema':
            return self._definition_schema()
        # fall back to base class __getattr__ defined in DexterityContent
        return super(MultiForm, self).__getattr__(name)
    
    def _normalize_date_value(self, field, data):
        """
        Normalize from data a date field; if data contains a singular
        string value, use the ColloquialDateConverter from uu.smartdate
        to convert, otherwise, parse the individual values for day, month,
        year from stock collective.z3cform.datetimewidget widget.
        """
        name = field.__name__
        if name in data:
            convert = ColloqialDateConverter(field, mkwidget(getRequest()))
            return convert.toFieldValue(unicode(data.get(name)))
        ## fallback: assume collective.z3cform.datetimewidget widget, three
        ## inputs for day, month, year respectively:
        v_day = name + '-day'
        v_month = name + '-month'
        v_year = name + '-year'
        year = data.get(v_year, None)
        month = data.get(v_month, None)
        day = data.get(v_day, None)
        _incomplete = lambda s: reduce(lambda a,b: and_(bool(a), bool(b)), s)
        if _incomplete((year, month, day)):
            return None
        return date(int(year), int(month), int(day))
    
    def _populate_record(self, entry, data):
        req = getRequest()
        changelog = []
        schema = entry.schema
        for name, field in getFieldsInOrder(schema):
            if IDate.providedBy(field):
                v = self._normalize_date_value(name, data)
                if v is not None:
                    field.validate(v)    # no enforcement of required here.
                setattr(entry, name, v)  # new value is possibly empty
                continue
            if name in data:
                value = data.get(name, None)
                cast_type = field_type(field)
                if cast_type:
                    if cast_type is int and isinstance(value, basestring):
                        value = value.replace(',','')
                    if cast_type is unicode and isinstance(value, str):
                        value = value.decode('utf-8')
                    elif (cast_type is datetime and
                          isinstance(value, basestring)):
                        fn = converter.DatetimeDataConverter(field,
                                                             TEXT_WIDGET)
                        value = fn.toFieldValue(unicode(value))
                    else:
                        try:
                            value = cast_type(value)
                        except (ValueError, TypeError):
                            pass
                if value not in (None, ''):
                    field.validate(value)
                    existing_value = getattr(entry, name, None)
                    if value != existing_value:
                        changelog.append(name)
                    setattr(entry, name, value)
                else:
                    #empty -> possible unset of previously set value in form?
                    setattr(entry, name, None)
        entry._p_changed = True #in case of collection fields
        if changelog:
            changelog = [Attributes(schema, name) for name in changelog]
            notify(ObjectModifiedEvent(entry, *changelog))
    
    def create(self, data=None):
        """ 
        Alternative factory for an IFormEntry object, does not store object.
        Should sign the entry with the schema of the form definition that
        this instance is bound to.
        
        If data is not None, copy fields from data matching schema fields,
        (note: superclass performs this by calling self._populate_record()).
        """
        form_schema = self._definition_schema()
        data = self._filtered_data(data, schema=form_schema)
        entry = RecordContainer.create(self, data)
        entry.sign(form_schema)
        return entry
    
    def _filtered_data(self, data, schema=None):
        """Filter fields for RecordContainer.update() to use"""
        if not data:
            return {}
        if schema is None:
            schema = self.definition_schema()
        _getv = lambda name: data.get(name, None)
        _indata = lambda name: name in data
        if IRecord.providedBy(data):
            _getv = lambda v: getattr(data, name, None)
            _indata = lambda name: hasattr(data, name)
        fieldnames = [k for k, field in getFieldsInOrder(schema)]
        fieldnames.append('record_uid')  # only non-schema attr we keep
        return dict([(k, _getv(k)) for k in fieldnames if _indata(k)])
    
    def _before_populate(self, record, data):
        current_signature = self._definition_signature() # TODO: optimize
        if record.signature != current_signature:
            # stale, update record signature to new definition schema
            current_schema = self._definition_schema()
            record.sign(current_schema)
    
    def _process_container_metadata(self, data):
        """
        Hook method called by uu.record.base.Record.update_all();
        used here to process notes for periodic form.
        """
        if 'notes' in data:
            notes = unicode(data['notes']).strip()
            if notes.strip():
                self.entry_notes = notes
                return True
        return False 
        
    # TODO: update handlers

