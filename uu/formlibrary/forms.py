from datetime import datetime, date

from Acquisition import aq_base
from collective.z3cform.datagridfield.interfaces import IDataGridField
from collective.z3cform.datagridfield.row import DictRow
import transaction
from persistent.dict import PersistentDict
from plone.dexterity.content import Item
from plone.autoform.form import AutoExtensibleForm
from plone.autoform.interfaces import WIDGETS_KEY
from plone.indexer.decorator import indexer
from plone.z3cform.fieldsets.group import GroupFactory
from plone.z3cform.fieldsets.interfaces import IGroupFactory
from z3c.form import form, field, button, converter, widget
from z3c.form.browser.radio import RadioFieldWidget
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from z3c.form.interfaces import IDataConverter
from z3c.form.testing import TestRequest
from zope.component import adapter, queryUtility, getMultiAdapter, queryAdapter
from zope.event import notify
from zope.interface import implements, implementer
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent import Attributes
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import IDate, IChoice, ICollection, IBool
from Products.CMFPlone.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage

from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE, DEFAULT_MODEL_XML
from uu.dynamicschema.interfaces import ISchemaSaver
from uu.record.base import RecordContainer
from uu.record.interfaces import IRecord

from uu.workflows.utils import history_log

from uu.formlibrary.browser.widget_overrides import TypeADateFieldWidget
from uu.formlibrary.definition import form_definition
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IBaseForm, IFormDefinition
from uu.formlibrary.interfaces import IFormComponents
from uu.formlibrary.interfaces import ISchemaProvider
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.record import FormEntry
from uu.formlibrary.utils import grid_wrapper_schema, normalize_usa_date
from uu.formlibrary.utils import WIDGET as GRID_WIDGET


# a widget object (ab)used for data converters from z3c.schema:
mkwidget = lambda request: widget.Widget(request)
TEXT_WIDGET = mkwidget(TestRequest())

# token for no value from select:
NOVALUE = '--NOVALUE--'


def field_type(field):
    if hasattr(field, '_type'):
        spec = field._type
        if isinstance(spec, tuple):
            return spec[0]
        if spec:
            return spec
    return None  # could not guess


flip = lambda s: (s[1], s[0])
invert = lambda s: map(flip, s)


def is_grid_wrapper_schema(schema):
    if 'data' in schema and WIDGETS_KEY in schema.getTaggedValueTags():
        widgets = schema.getTaggedValue(WIDGETS_KEY)
        if 'data' in widgets and widgets['data'] == GRID_WIDGET:
            return True
    return False


def common_widget_updates(context):
    """
    Given a context, update field widgets for it.  Context
    May be any z3c.form instance or a field group contained
    within.
    """
    # form field filter definition:
    vtype = lambda formfield: getattr(formfield.field, 'value_type', None)
    use_vocab = lambda v: hasattr(v, '__len__') and hasattr(v, '__iter__')
    is_choice = lambda formfield: IChoice.providedBy(formfield.field)
    v_choice = lambda formfield: IChoice.providedBy(vtype(formfield))
    is_collection = lambda formfield: ICollection.providedBy(formfield.field)
    is_multi = lambda formfield: is_collection(formfield) and v_choice(formfield)  # noqa
    is_date = lambda formfield: IDate.providedBy(formfield.field)
    is_bool = lambda formfield: IBool.providedBy(formfield.field)

    # filtered lists of form fields by type
    formfields = context.fields.values()
    choicefields = filter(is_choice, formfields)
    multifields = filter(is_multi, formfields)
    datefields = filter(is_date, formfields)
    boolfields = filter(is_bool, formfields)

    for formfield in choicefields:
        vocab = formfield.field.vocabulary
        if use_vocab(vocab) and len(vocab) <= 3:
            formfield.widgetFactory = RadioFieldWidget

    for formfield in multifields:
        vocab = formfield.field.value_type.vocabulary
        if use_vocab(vocab) and len(vocab) <= 16:
            formfield.widgetFactory = CheckBoxFieldWidget

    for formfield in datefields:
        formfield.widgetFactory = TypeADateFieldWidget

    for formfield in boolfields:
        formfield.widgetFactory = RadioFieldWidget


# form-related adapters:

@implementer(IFormDefinition)
@adapter(IBaseForm)
def metadata_form_definition(form):
    """Named adapter for metadata"""
    try:
        primary = IFormDefinition(form)
        return form_definition(primary, attr='metadata_definition')
    except ValueError:
        return None  # since metadata definition is optional


@indexer(IBaseForm)
def title_indexer(context):
    title = context.Title()
    parent = getattr(context, '__parent__', None)
    if parent is None:
        return title
    supplement = parent.Title()
    return '%s - %s' % (title, supplement)


@indexer(IBaseForm)
def form_references(context):
    return [context.definition]


class ComposedForm(AutoExtensibleForm, form.Form):
    """
    A form composed from multiple schema adapting a form definition.
    This composition uses (base class from) plone.autoform to compose
    a merged form.
    """

    ignoreContext = True    # form operates without edit context.

    # autoGroups here requires plone.autoform >= 1.6 for anonymous schema:
    autoGroups = True

    enable_form_tabbing = False  # do not display fieldsets in tabs.

    # schema must be property, not attribute for AutoExtensibleForm sublcass
    @property
    def schema(self):
        return self._schema

    @property
    def additionalSchemata(self):
        return self._additionalSchemata

    def __init__(self, context, request, name=None):
        """
        Construct composed form given (default) schema an a tuple
        of ordered additional schema key/value pairs of (string)
        component name keys to schema values.
        """
        self.context = context
        self.request = request
        # form definition will either be context, or adaptation of context.
        # see uu.formlibrary.definition.form_definition for adapter example.
        if name is None:
            self.definition = IFormDefinition(self.context)
        else:
            self.definition = queryAdapter(
                self.context,
                IFormDefinition,
                name=name,
                )
        self._schema = self.definition.schema
        self.groups = []  # modified by updateFieldsFromSchemata()

        self.components = IFormComponents(self.definition)
        self.group_schemas = self._group_schemas()
        self.group_titles = self._group_titles()

        # mapping: schema to names:
        self.schema_names = dict(invert(self.group_schemas))

        # ordered list of additional schema for AutoExtensibleForm:
        self._additionalSchemata = tuple(
            [t[1] for t in self.group_schemas if t[0]]
            )
        # super(ComposedForm, self).__init__(self, context, request)
        form.Form.__init__(self, context, request)
        self.saved = False  # initial value: no duplication of save...
        self.save_attempt = False  # flag for save attempt, success or not
        self._status = IStatusMessage(self.request)

    def _group_schemas(self):
        result = []
        for name in self.components.names:
            group = self.components.groups[name]
            schema = group.schema
            if group.group_usage == u'grid':
                schema = grid_wrapper_schema(schema)
            result.append((name, schema))
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
                continue  # default, we don't need another group
            title = self.group_titles.get(name, name)
            fieldset_group = GroupFactory(name, field.Fields(), title)
            self.groups.append(fieldset_group)
        super(ComposedForm, self).updateFieldsFromSchemata()

    def _load_widget_data(self):
        _marker = object()
        data = aq_base(self.context).data
        groups = dict((g.__name__, g) for g in self.groups)
        groupnames = [''] + groups.keys()
        for groupname in groupnames:
            group_data = data.get(groupname, None)
            if groupname is '':
                group = self
            else:
                group = groups.get(groupname)
                fieldgroup = self.definition[groupname]
                # # plone.autoform binds groups really, really late, so
                # # we are stuck with a GroupFactory object, we need to
                # # call it to get the actual group, then replace the
                # # group factory with it once we have manipulated
                # # any widget values:
                if IGroupFactory.providedBy(group):
                    idx = self.groups.index(group)
                    actual_group = group(self.context, self.request, self)
                    self.groups[idx] = group = actual_group
                    group.update()  # will populate group.widgets
                if group_data and fieldgroup.group_usage == 'grid':
                    data_widget = group.widgets.values()[0]
                    data_widget.value = getattr(group_data, 'data', [])
                    continue

            if group_data is not None:
                for formfield in group.fields.values():
                    schema_field = formfield.field
                    widgetname = formfield.__name__
                    fieldname = schema_field.__name__
                    v = getattr(group_data, fieldname, _marker)
                    if v is not _marker:
                        widget = group.widgets.get(widgetname)
                        conv = getMultiAdapter(
                            (schema_field, widget),
                            IDataConverter,
                        )
                        if not IDataGridField.providedBy(widget):
                            v = conv.toWidgetValue(v)
                        widget.value = v
                        if hasattr(widget, 'update'):
                            # may be necessary to copy value to other state,
                            # as is the case with radio button widgets
                            widget.update()
                            # multiple collection like set/list (multi-choice)
                            # has issues where SequenceWidget wants to reset
                            # widget.value during update... so we have to
                            # check the value (ugly hack) and also re-set the
                            # value for the display widget:
                            if ICollection.providedBy(schema_field):
                                widget.value = v
                                if v:
                                    term_item = [
                                        t for t in widget.items
                                        if t.get('value') == v[0]
                                    ][0]
                                    term_item['checked'] = True

    def updateWidgets(self):
        common_widget_updates(self)
        for group in self.groups:
            common_widget_updates(group)
        super(ComposedForm, self).updateWidgets()
        # # finally, if non-defintion context, set widget values via group data
        if not IFormDefinition.providedBy(self.context):
            self._load_widget_data()

    def datagridInitialise(self, subform, widget):
        if not hasattr(self, '_widgets_initialized'):
            self._widgets_initialized = []  # don't duplicate effort!
        if subform not in self._widgets_initialized:
            date_fields = [f for f in subform.fields.values()
                           if IDate.providedBy(f.field)]
            for formfield in date_fields:
                formfield.widgetFactory = TypeADateFieldWidget
        self._widgets_initialized.append(subform)

    def getPrefix(self, schema):
        if schema in self.schema_names:
            return self.schema_names[schema]
        # fall-back will not work for anoymous schema without names, but
        # it is the best we can assume to do here:
        return super(ComposedForm, self).getPrefix(schema)

    def _saveResult(self, result):
        schemas = dict(self.group_schemas)
        for name, values in result.items():
            name = str(name)
            schema = schemas.get(name, self._schema)  # schema or default group
            if schema:
                group_record = self.context.data.get(name, None)
                if group_record is None:
                    group_record = self.context.data[name] = FormEntry()
                group_record.sign(schema)
                for fieldname, value in values.items():
                    setattr(group_record, fieldname, value)

    def _handleSave(self, action, msg='Saved form data'):
        self.save_attempt = True
        data, errors = self.extractData()
        if errors or IFormDefinition.providedBy(self.context) or self.saved:
            return False  # just validate if errors, or if context if defn
        if not self.saved:
            result = {}  # submitted data. k: group name; v: dict of name/value
            group_keys = []
            for group in self.groups:
                groupdata = {}
                form_group_data = group.extractData()[0]
                for name, _field in group.fields.items():
                    group_keys.append(name)
                    fieldname = _field.field.__name__
                    default = getattr(_field.field, 'default', None)
                    field_data = form_group_data.get(name, default)
                    if ICollection.providedBy(_field.field):
                        if isinstance(_field.field.value_type, DictRow):
                            is_nonempty_row = lambda v: any(v.values())
                            field_data = filter(is_nonempty_row, field_data)
                    groupdata[fieldname] = field_data
                result[group.__name__] = groupdata
            # filter default fieldset values, ignore group values in data dict:
            result[''] = dict([(k, v) for k, v in data.items()
                               if k not in group_keys])
            self._saveResult(result)
            self.saved = True
            history_log(self.context, message=msg, set_modified=True)
            notify(ObjectModifiedEvent(self.context))
            transaction.get().note(msg)
        self._status.addStatusMessage('Saved form data', type='info')
        return True

    @button.buttonAndHandler(
        u'\u2714 Save draft',
        condition=lambda form: form.mode == 'input'
        )
    def handleSave(self, action):
        self._handleSave(action)

    @button.buttonAndHandler(
        u'\u21E5 Save and submit',
        condition=lambda form: form.mode == 'input'
        )
    def handleSaveSubmit(self, action):
        saved = self._handleSave(action)
        if not saved:
            return   # no status change, no 302 -- validation errors to user
        wftool = getToolByName(self.context, 'portal_workflow')
        chain = wftool.getChainFor(self.context)[0]
        state = wftool.getStatusOf(chain,
                                   self.context)['review_state']
        if state == 'visible':
            wftool.doActionFor(self.context, 'submit')
            self.context.reindexObject()
            self._status.addStatusMessage(
                'Form submitted for review',
                type='info'
                )
            url = self.context.absolute_url()
            self.request.RESPONSE.redirect(url)


# # content-type implementations for form instances:

class SimpleForm(Item):
    """
    Single-record form instance tied to a specific form definition and its
    schema.
    """

    portal_type = SIMPLE_FORM_TYPE

    implements(ISimpleForm)

    def __init__(self, id=None, *args, **kwargs):
        super(SimpleForm, self).__init__(id, *args, **kwargs)
        self.data = PersistentDict()  # of FormEntry()
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
    >>> from zope.component.hooks import getSite
    >>> portal = getSite()  # (for testing: set up by plone.testing layer)
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

    >>> series = portal['form_series']
    >>> multi_form = series['multi']
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
    >>> from zope.lifecycleevent import ObjectCreatedEvent
    >>> from zope.event import notify
    >>> notify(ObjectModifiedEvent(definition))  # => schema load from xml
    >>> assert definition.signature != DEFAULT_SIGNATURE  # new schema, sig
    >>> assert serializeSchema(definition.schema) == monkey_xml

    Now, since we bound multi_form.definition to the UUID of the definition
    that just had its schema re-loaded, we can see this indirectly on
    the multi_form instance:

    >>> assert multi_form._definition_schema() is definition.schema
    >>> assert multi_form.schema is definition.schema

    Multi forms are record containers, and thus have length and
    containment checks for records within:

    >>> assert len(multi_form) == 0
    >>> import uuid  # keys for entries are stringified UUIDs
    >>> randomuid = str(uuid.uuid4())
    >>> assert randomuid not in multi_form
    >>> assert multi_form.get(randomuid, None) is None

    And (as record containers) they have keys/values/items like a mapping:

    >>> assert multi_form.keys() == ()
    >>> assert multi_form.values() == ()
    >>> assert multi_form.items() == ()  # of course, these are empty now.

    Before we add row/record items, we need to create them; there are
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
    >>> assert entry3.count == 3  # default field value via __getattr__ proxy

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

    Of course, merely using the multi form object as a factory for new entries
    does not mean the entries are stored within (yet):

    >>> assert entry4.record_uid not in multi_form
    >>> assert entry4.record_uid not in multi_form.keys()

    Let's add an item to the multi-form (record container):

    >>> multi_form.add(entry4)

    There are two ways to check for containment, by either key or value:

    >>> assert entry4 in multi_form
    >>> assert entry4.record_uid in multi_form

    We can get records using a (limited, read) mapping-like interface:

    >>> assert len(multi_form) == 1  # we just added the first entry
    >>> assert multi_form.values()[0] is entry4
    >>> assert multi_form.get(entry4.record_uid) is entry4
    >>> assert multi_form[entry4.record_uid] is entry4

    We can deal with references to entries also NOT in the container:

    >>> import uuid
    >>> randomuid = str(uuid.uuid4())
    >>> assert randomuid not in multi_form
    >>> assert multi_form.get(str(uuid.uuid4()), None) is None
    >>> assert entry1.record_uid not in multi_form

    And we can check containment on either an instance or a UID; checking on
    an instance is just a convenience that uses its UID (record_uid) field
    to check for actual containment:

    >>> assert entry4.record_uid in multi_form
    >>> assert entry4 in multi_form  # shortcut!

    However, it should be noted for good measure:

    >>> assert entry4 in multi_form.values()
    >>> assert entry4.record_uid in multi_form.keys()
    >>> assert entry4 not in multi_form.keys()  # of course!
    >>> assert (entry4.record_uid, entry4) in multi_form.items()

    We can modify an entry contained directly; this is the most direct and
    low-level update interface for any entry:

    >>> assert entry4.title is None
    >>> entry4.title = u'Curious George'
    >>> assert multi_form.get(entry4.record_uid).title == u'Curious George'

    We can add another record:

    >>> multi_form.add(entry6)
    >>> assert entry6 in multi_form
    >>> assert entry6.record_uid in multi_form
    >>> assert len(multi_form) == 2

    Keys, values, items are always ordered; since we added entry4, then
    entry6 previously, they will return in that order:

    >>> expected_order = (entry4, entry6)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(multi_form.keys()) == expected_uid_order
    >>> assert tuple(multi_form.values()) == expected_order
    >>> assert tuple(multi_form.items()) == expected_items_order

    We can re-order this; let's move entry6 up to position 0 (first):

    >>> multi_form.reorder(entry6, offset=0)
    >>> expected_order = (entry6, entry4)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(multi_form.keys()) == expected_uid_order
    >>> assert tuple(multi_form.values()) == expected_order
    >>> assert tuple(multi_form.items()) == expected_items_order

    We can also re-order by UID instead of record/entry reference:

    >>> multi_form.reorder(entry6.record_uid, offset=1)  # where it was before
    >>> expected_order = (entry4, entry6)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(multi_form.keys()) == expected_uid_order
    >>> assert tuple(multi_form.values()) == expected_order
    >>> assert tuple(multi_form.items()) == expected_items_order

    And we can remove records from containment by UID or by reference (note,
    we use __delitem__() method of a writable mapping):

    >>> del(multi_form[entry6])
    >>> assert entry6 not in multi_form
    >>> assert entry6.record_uid not in multi_form
    >>> assert len(multi_form) == 1
    >>> assert entry4 in multi_form
    >>> del(multi_form[entry4.record_uid])
    >>> assert entry4 not in multi_form
    >>> assert len(multi_form) == 0

    Earlier, direct update of objects was demonstrated: get an object and
    modify its properties.  This attribute-setting mechanism is the best
    low-level interface, but it does not (a) support a wholesale update
    from either a field dictionary/mapping nor another object providing
    IFormEntry needing its form data to be copied; nor (b) support
    notification of zope.lifecycle object events.

    Given these needs, a high level interface for update exists, with the
    multi form object acting as a controller for updating contained entries.
    This provides for update via another entry (a field-by-field copy) or
    from a data dictionary/mapping.

    Let's reuse an existing entry and the IMonkey interface defined above to
    test the update() interface with appropriate data.

    >>> newuid = str(uuid.uuid4())
    >>> data = {    'record_uid' : newuid,
    ...             'title'      : u'George',
    ...             'count'      : 9,
    ...        }
    >>> assert len(multi_form) == 0  # empty, nothing in there yet!
    >>> assert newuid not in multi_form


    Note, update() returns an entry; return value can be ignored if caller
    deems it not useful.

    >>> entry = multi_form.update(data)
    >>> assert newuid in multi_form  # update implies adding!
    >>> assert entry is multi_form.get(newuid)
    >>> assert entry.title == data['title']
    >>> assert entry.count == data['count']

    Now, the entry we just modified was also added.  We can modify it again:

    >>> data = {    'record_uid' : newuid,
    ...             'title'      : u'Curious George',
    ...             'count'      : 2,
    ...        }
    >>> entry = multi_form.update(data)
    >>> assert newuid in multi_form     # same uid
    >>> entry.title
    u'Curious George'
    >>> entry.count
    2
    >>> assert len(multi_form) == 1     # same length, nothing new was added.

    We could also create a stand-in entry for which data is copied to the
    permanent entry with the same UUID on update:

    >>> temp_entry = multi_form.create()
    >>> temp_entry.record_uid = newuid      # overwrite with the uid of entry
    >>> temp_entry.title = u'Monkey jumping on the bed'
    >>> temp_entry.count = 0

    temp_entry is a stand-in which we will pass to update(), when we really
    intend to modify entry (they have the same UID):

    >>> real_entry = multi_form.update(temp_entry)
    >>> assert multi_form.get(newuid) is not temp_entry
    >>> assert multi_form.get(newuid) is entry  # still the same object...
    >>> assert multi_form.get(newuid) is real_entry
    >>> entry.title                             # ...but data is modified!
    u'Monkey jumping on the bed'
    >>> entry.count
    0
    >>> assert len(multi_form) == 1     # same length, nothing new was added.

    Basic data normalization
    ------------------------

    update() supports basic data normalization for string input that should
    be converted to unicode (using utf-8), and for z3c.form's string
    serialization of date and datetime objects [1].

        [1] http://pypi.python.org/pypi/z3c.form# date-data-converter

    Let's create a new definition fixture to demonstrate usage:

    >>> formlibrary = portal['formlib']
    >>> definition2 = formlibrary.invokeFactory(
    ...     'uu.formlibrary.definition',
    ...     id='def2',
    ...     )
    >>> definition2 = formlibrary['def2']
    >>> assert IFormDefinition.providedBy(definition2)

    Give the definition this schema:

    >>> class IParty(Interface):
    ...     name = schema.TextLine()
    ...     birthday = schema.Date()
    ...     party_time = schema.Datetime()
    ...
    >>> IParty.__name__ = None  # make anonymous schema like used in reality
    >>> definition2.entry_schema = serializeSchema(IParty)
    >>> notify(ObjectModifiedEvent(definition2))  # => sync of new schema
    >>> from zope.schema import getFieldNamesInOrder
    >>> assert 'birthday' in getFieldNamesInOrder(definition2.schema)

    Now we need a new form to use this definition:

    >>> party_form = MultiForm()
    >>> notify(ObjectCreatedEvent(party_form))
    >>> party_form.definition = IUUID(definition2)
    >>> assert 'birthday' in party_form.schema      # yep, the same schema
    >>> assert party_form.schema is definition2.schema  # just to be sure

    Now we need a new form to use this definition:

    >>> party_form = MultiForm()
    >>> notify(ObjectCreatedEvent(party_form))
    >>> party_form.definition = IUUID(definition2)
    >>> assert 'birthday' in party_form.schema      # yep, the same schema
    >>> assert party_form.schema is definition2.schema  # just to be sure

    Then create an entry using the newly created form form context:

    >>> entry = party_form.create()

    The entry was signed by party_form.create() using party_form.schema,
    thus the entry provides the bound definition's schema:

    >>> assert definition2.schema.providedBy(entry)
    >>> assert hasattr(entry, 'birthday')

    Finally, set some data that needs normalization (strings and date[time]):

    >>> data = {
    ...     'record_uid': entry.record_uid,  # which record to update
    ...     'name'      : 'Me',
    ...     'birthday'  : u'06/01/1977',
    ...     'party_time': u'11/06/05 12:00',
    ...     }
    >>> entry = party_form.update(data)
    >>> assert definition2.schema.providedBy(entry)
    >>> assert isinstance(entry.name, unicode)
    >>> entry.name  # converted to unicode from string via utf-8 decode.
    u'Me'
    >>> entry.birthday
    datetime.date(1977, 6, 1)
    >>> entry.party_time
    datetime.datetime(2011, 6, 5, 12, 0)


    JSON integration
    ----------------

    As a convenience, update_all() parses JSON into a data dict for use by
    update(), using the Python 2.6 json library (aka/was: simplejson):

    >>> import json  # requires Python >= 2.6
    >>> data['name'] = 'Chunky monkey'
    >>> serialized = json.dumps([data,], indent=2)  # JSON array of one item...
    >>> print serialized  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    [
      {
        "party_time": "11/06/05 12:00",
        "birthday": "06/01/1977",
        "name": "Chunky monkey",
        "record_uid": "..."
      }
    ]


    The JSON created above is useful enough for demonstration, despite being
    only a single-item list.

    >>> entry.name  # before
    u'Me'
    >>> party_form.update_all(serialized)
    >>> entry.name  # after update
    u'Chunky monkey'

    update_all() also takes a singular record, not just a JSON array:

    >>> data['name'] = 'Curious George'
    >>> serialized = json.dumps(data, indent=2)  # JSON object, not array.
    >>> print serialized  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    {
      "party_time": "11/06/05 12:00",
      "birthday": "06/01/1977",
      "name": "Curious George",
      "record_uid": "..."
    }
    >>> entry.name  # before
    u'Chunky monkey'
    >>> party_form.update_all(serialized)
    >>> entry.name  # after update
    u'Curious George'

    JSON parsing also supports a "bundle" or wrapper object around a list of
    entries, where the wrapper contains metadata about the form itself, not
    its entries (currently, this is just the entry_notes field, which
    is sourced from the JSON bundle/wrapper object field called 'notes').
    When wrapped, the list of entries is named 'entries' inside the wrapper.

    >>> data['name'] = u'Party monkey'
    >>> serialized = json.dumps({'notes'    : 'something changed',
    ...                          'entries'  : [data,]},
    ...                         indent=2)  # JSON array of one item...
    >>> entry.name  # before
    u'Curious George'
    >>> assert party_form.entry_notes is None  # field default is None
    >>> party_form.update_all(serialized)
    >>> entry.name  # after
    u'Party monkey'
    >>> party_form.entry_notes
    u'something changed'

    It should be noted that update_all() removes entries not in the data
    payload, and it preserves the order contained in the JSON entries.

    Metadata definition
    -------------------

    A multi-record form may have global metadata about it -- not per-record.
    In order to make this user-extensible, a similar mechanism must
    exist to provide a form definition for use in metadata.

    Initially, our form here has a definition, but no definition for metadata:

    >>> defn = IFormDefinition(party_form)
    >>> assert aq_base(defn) is aq_base(definition2)
    >>> assert getattr(defn, 'metadata_definition', None) is None
    >>> from zope.component import queryAdapter
    >>> assert queryAdapter(defn, IFormDefinition, 'metadata') is None
    >>> assert queryAdapter(party_form, IFormDefinition, 'metadata') is None

    Let's assign a definition for metadata:

    >>> defn.metadata_definition = IUUID(definition)
    >>> meta_defn = queryAdapter(defn, IFormDefinition, 'metadata')
    >>> assert meta_defn is not None
    >>> meta_defn = queryAdapter(party_form, IFormDefinition, 'metadata')
    >>> assert meta_defn is not None
    >>> assert aq_base(meta_defn) is aq_base(definition)

    ComposedForm adapter can be created to manage metadata:

    >>> from uu.formlibrary.tests import test_request
    >>> req = test_request()
    >>> composed = ComposedForm(party_form, req, name='metadata')
    >>> assert aq_base(composed.definition) is aq_base(meta_defn)

    Note: update of actual metadata is responsibility of views and/or
    ComposedForm adapters on the form.  RecordContainer.update() does
    not handle metadata, only record data.

    Object events
    -------------

    CRUD methods on a controlling object should have some means of extension,
    pluggable to code that should subscribe to CRUD (object lifecycle) events.
    We notify four distinct zope.lifecycleevent object event types:

    1. Object created (zope.lifecycleevent.interfaces.IObjectCreatedEvent)

    2. Object addded to container (the MultiForm form object):
        (zope.lifecycleevent.interfaces.IObjectAddedEvent).

    3. Object modified (zope.lifecycleevent.interfaces.IObjectModifiedEvent)

    4. Object removed (zope.lifecycleevent.interfaces.IObjectRemovedEvent)

    Note: the create() operation both creates and modifies: as such, both
    created and modified events are fired off, and since most creations also
    are followed by an add() to a form, you may have three events to
    subscribe to early in a new entry's lifecycle.

    First, some necessary imports of events and the @adapter decorator:

    >>> from zope.component import adapter
    >>> from zope.lifecycleevent import IObjectCreatedEvent
    >>> from zope.lifecycleevent import IObjectModifiedEvent
    >>> from zope.lifecycleevent import IObjectRemovedEvent
    >>> from zope.lifecycleevent import IObjectAddedEvent

    Let's define dummy handlers:

    >>> @adapter(IFormEntry, IObjectCreatedEvent)
    ... def handle_create(context, event):
    ...     print 'object created'
    ...
    >>> @adapter(IFormEntry, IObjectModifiedEvent)
    ... def handle_modify(context, event):
    ...     print 'object modified'
    ...
    >>> @adapter(IFormEntry, IObjectRemovedEvent)
    ... def handle_remove(context, event):
    ...     print 'object removed'
    ...
    >>> @adapter(IFormEntry, IObjectAddedEvent)
    ... def handle_add(context, event):
    ...     print 'object added'
    ...

    Now, let's register the handlers:
    >>> for h in (handle_create, handle_modify, handle_remove, handle_add):
    ...     sm.registerHandler(h)
    ...

    We can watch these event handlers get fired when CRUD methods are called.

    Object creation, with and without data:

    >>> newentry = multi_form.create()      # should print 'object created'
    object created
    >>> another_uid = str(uuid.uuid4())
    >>> newentry = multi_form.create({'count':88})
    object modified
    object created

    Object addition:

    >>> multi_form.add(newentry)
    object added
    >>>

    Object removal:

    >>> del(multi_form[newentry.record_uid])
    object removed

    Object update (existing object):

    >>> entry = multi_form.values()[0]
    >>> entry = multi_form.update({'record_uid' : entry.record_uid,
    ...                            'title'      : u'Me'})
    object modified

    Object modified (new object or not contained):

    >>> random_uid = str(uuid.uuid4())
    >>> entry = multi_form.update({'record_uid' : random_uid,
    ...                            'title'      : u'Bananas'})
    object modified
    object created
    object added

    Event handlers for modification can know what fields are modified; let's
    create a more interesting modification handler that prints the names of
    changed fields.

    >>> from zope.lifecycleevent.interfaces import IAttributes
    >>> unregistered = sm.unregisterHandler(handle_modify)
    >>> @adapter(IFormEntry, IObjectModifiedEvent)
    ... def handle_modify(context, event):
    ...     if event.descriptions:
    ...         attr_desc = [d for d in event.descriptions
    ...                         if (IAttributes.providedBy(d) and
    ...                             d.interface is definition.schema)]
    ...         if attr_desc:
    ...             field_names = attr_desc[0].attributes
    ...             print tuple(field_names)
    >>> sm.registerHandler(handle_modify)

    >>> entry = multi_form.values()[0]
    >>> entry = multi_form.update({'record_uid' : entry.record_uid,
    ...                            'title'      : u'Hello'})
    ('title',)

    Finally, clean up and remove all the dummy handlers:
    >>> for h in (handle_create, handle_modify, handle_remove, handle_add):
    ...     success = sm.unregisterHandler(h)
    ...


    """

    portal_type = MULTI_FORM_TYPE
    catalog = None  # instances may override, via handler usually

    implements(IMultiForm, ISchemaProvider)

    def __init__(self, id=None, **kwargs):
        Item.__init__(self, id, **kwargs)
        self._metadata = PersistentDict()
        RecordContainer.__init__(self, factory=FormEntry)

    @property
    def data(self):
        """
        Compatibility shim for using ComposedForm adapter for
        multi-record form metadata; setting self._metadata on
        instance where it does not previously exist avoids need
        for a migration.
        """
        if getattr(self, '_metadata', None) is None:
            self._metadata = PersistentDict()
        return self._metadata

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
        string value, try USA mm/dd/yyyy and ISO 8601 (assume mockup widget)
        to convert, otherwise, parse the individual values for day, month,
        year from stock collective.z3cform.datetimewidget widget.
        """
        v = data.get(field.__name__, None)
        if v is None:
            return None
        v = v.strip()
        # TODO: we may consider removing non-ISO support altogether TBD:
        usadate = normalize_usa_date(data.get(field.__name__))
        if usadate is not None:
            return usadate
        # assume ISO 8601, which should be the case with mockup2 widgets
        parts = v[:10].split('-')
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        return date(year, month, day)

    def _populate_record(self, entry, data):
        changelog = []
        schema = entry.schema
        for name, _field in getFieldsInOrder(schema):
            if IDate.providedBy(_field):
                v = self._normalize_date_value(_field, data)
                if v is not None:
                    _field.validate(v)    # no enforcement of required here.
                setattr(entry, name, v)  # new value is possibly empty
                continue
            if name in data:
                value = data.get(name, None)
                if value in (u'true', u'false') and IBool.providedBy(_field):
                    value = True if value == 'true' else False  # radio widget
                if value == NOVALUE:
                    value = None
                cast_type = field_type(_field)
                if cast_type:
                    if cast_type is int and isinstance(value, basestring):
                        value = value.replace(',', '')
                    if cast_type is unicode and isinstance(value, str):
                        value = value.decode('utf-8')
                    elif (cast_type is datetime and
                          isinstance(value, basestring)):
                        fn = converter.DatetimeDataConverter(_field,
                                                             TEXT_WIDGET)
                        value = fn.toFieldValue(unicode(value))
                    else:
                        try:
                            value = cast_type(value)
                        except (ValueError, TypeError):
                            pass
                if value not in (None, ''):
                    _field.validate(value)
                    existing_value = getattr(entry, name, None)
                    if value != existing_value:
                        changelog.append(name)
                    setattr(entry, name, value)
                else:
                    # empty -> possible unset of previously set value in form?
                    setattr(entry, name, None)
        entry._p_changed = True  # in case of collection fields
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
            schema = self._definition_schema()
        _getv = lambda name: data.get(name, None)
        _indata = lambda name: name in data
        if IRecord.providedBy(data):
            _getv = lambda name: getattr(data, name, None)
            _indata = lambda name: hasattr(data, name)
        fieldnames = [k for k, field in getFieldsInOrder(schema)]
        fieldnames.append('record_uid')  # only non-schema attr we keep
        return dict([(k, _getv(k)) for k in fieldnames if _indata(k)])

    def _before_populate(self, record, data):
        current_signature = self._definition_signature()  # TODO: optimize
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
            if notes.strip() or self.entry_notes:
                self.entry_notes = notes
                return True
        return False

