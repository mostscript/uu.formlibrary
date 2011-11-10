from plone.dexterity.content import Item
from zope.app.component.hooks import getSite
from zope.component import adapter
from zope.interface import implements, implementer
from Products.CMFPlone.utils import getToolByName

from uu.dynamicschema.schema import new_schema
from uu.dynamicschema.interfaces import DEFAULT_SIGNATURE
from uu.record.base import RecordContainer
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IBaseForm, IFormDefinition
from uu.formlibrary.interfaces import DEFINITION_TYPE
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.record import FormEntry


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

