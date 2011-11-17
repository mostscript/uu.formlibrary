from persistent.dict import PersistentDict
from plone.dexterity.content import Item
from plone.autoform.form import AutoExtensibleForm
from plone.autoform.interfaces import WIDGETS_KEY
from plone.z3cform.fieldsets.group import GroupFactory
from z3c.form import form, field
from zope.app.component.hooks import getSite
from zope.component import adapter
from zope.interface import implements, implementer
from Products.CMFPlone.utils import getToolByName

from uu.dynamicschema.schema import new_schema
from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE
from uu.record.base import RecordContainer
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

        #self.group_schemas = self._field_group_schemas()
        # mapping: names to schema:
        #self.components = dict( [('', self._schema),] + self.group_schemas )
        # mapping: schema to names:
        #self.schema_names = dict(invert(self.components.items()))
        
        self.schema_names = dict(invert(self.group_schemas))

        # ordered list of additional schema for AutoExtensibleForm:
        self._additionalSchemata = tuple(
            [t[1] for t in self.group_schemas if t[0]]
            )
        #super(ComposedForm, self).__init__(self, context, request)
        form.Form.__init__(self, context, request)
   
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
    
    def _field_group_schemas(self):
        """Get list of field group schemas from form definition context"""
        result = []
        groups = filter(is_field_group, self.definition.objectValues())
        for group in groups:
            if group.group_usage == u'grid':
                wrapper = grid_wrapper_schema(group.schema)
                result.append(
                    (group.getId(), wrapper,)
                    )
            else:
                result.append( (group.getId(), group.schema,) )
            self.group_titles[group.getId()] = group.Title()
        return result
    
    def getPrefix(self, schema):
        if schema in self.schema_names:
            return self.schema_names[schema]
        # fall-back will not work for anoymous schema without names, but
        # it is the best we can assume to do here:
        return super(ComposedForm, self).getPrefix(schema)


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

