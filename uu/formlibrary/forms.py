from plone.dexterity.content import Item
from plone.autoform.form import AutoExtensibleForm
from z3c.form import form
from zope.app.component.hooks import getSite
from zope.component import adapter
from zope.interface import implements, implementer
from Products.CMFPlone.utils import getToolByName

from uu.dynamicschema.schema import new_schema
from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE
from uu.record.base import RecordContainer
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IBaseForm, IFormDefinition
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.record import FormEntry
from uu.formlibrary.utils import grid_wrapper_schema


flip = lambda a,b: (b,a)
invert = lambda s: reduce(flip, s)

is_field_group = lambda o: o.portal_type == FIELD_GROUP_TYPE


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
    
    ignoreContext = True    # form operates 
    
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
        group_schemas = self._field_group_schemas()
        # mapping: names to schema:
        self.components = dict( [('default', self._schema),] + group_schemas )
        # mapping: schema to names:
        self.schema_names = dict(invert(self.components.items()))
        # ordered list of additional schema for AutoExtensibleForm:
        self._additionalSchemata = tuple([t[1] for t in group_schemas])
        #super(ComposedForm, self).__init__(self, context, request)
        form.Form.__init__(self, context, request)
    
    def _field_group_schemas(self):
        """Get list of field group schemas from form definition context"""
        result = []
        groups = filter(is_field_group, self.definition.objectValues())
        for group in groups:
            if group.group_usage == 'grid':
                result.append(
                    (group.getId(), grid_wrapper_schema(group.schema),)
                    )
            else:
                result.append( (group.getId(), group.schema,) )
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
        self.data = FormEntry()

    #TODO: DRY
    def _schema(self):
        try:
            definition = form_definition(self) #TODO: indirect interface-adaptation
        except ValueError:
            return new_schema()
        return definition.schema
   
    def _signature(self):
        try:
            definition = form_definition(self) #TODO: indirect interface-adaptation
        except ValueError:
            return DEFAULT_SIGNATURE
        return definition.signature
    
    def __getattr__(self, name):
        """Hack in lieu of Python property self.schema"""
        if name == 'schema':
            return self._schema()
        if name == 'signature':
            return self._signature()
        # fall back to base class(es) __getattr__ from DexterityContent
        return super(SimpleForm, self).__getattr__(name)


class MultiForm(Item, RecordContainer):
    """
    Multi-record form instance tied to a specific form definition and its
    schema.  Acts as a record container.
    """
   
    portal_type = MULTI_FORM_TYPE

    implements(IMultiForm)
    
    #TODO: DRY
    def _schema(self):
        try:
            definition = form_definition(self) #TODO: indirect interface-adaptation
        except ValueError:
            return new_schema()
        return definition.schema
   
    def _signature(self):
        try:
            definition = form_definition(self) #TODO: indirect interface-adaptation
        except ValueError:
            return DEFAULT_SIGNATURE
        return definition.signature
    
    def __getattr__(self, name):
        """Hack in lieu of Python property self.schema"""
        if name == 'schema':
            return self._schema()
        if name == 'signature':
            return self._signature()
        # fall back to base class(es) __getattr__ from DexterityContent
        return super(MultiForm, self).__getattr__(name)

