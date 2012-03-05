import transaction
from persistent.dict import PersistentDict
from plone.dexterity.content import Item
from plone.autoform.form import AutoExtensibleForm
from plone.autoform.interfaces import WIDGETS_KEY
from plone.z3cform.fieldsets.group import GroupFactory
from z3c.form import form, field, button
from zope.app.component.hooks import getSite
from zope.component import adapter
from zope.interface import implements, implementer
from zope.schema.interfaces import IDate
from DateTime import DateTime
from Products.CMFPlone.utils import getToolByName

from uu.dynamicschema.schema import new_schema
from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE
from uu.record.base import RecordContainer
from uu.smartdate.browser.widget import SmartdateFieldWidget
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IBaseForm, IFormDefinition
from uu.formlibrary.interfaces import IFormComponents
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.record import FormEntry
from uu.formlibrary.utils import grid_wrapper_schema
from uu.formlibrary.utils import WIDGET as GRID_WIDGET


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
    """
   
    portal_type = MULTI_FORM_TYPE

    implements(IMultiForm)

