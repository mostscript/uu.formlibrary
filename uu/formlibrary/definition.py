from zope.interface import implements
from plone.dexterity.content import Container, Item
from plone.schemaeditor.browser.schema.traversal import SchemaContext
from persistent.list import PersistentList

from uu.dynamicschema.schema import SignatureSchemaContext
from uu.dynamicschema.schema import copy_schema

from uu.formlibrary.interfaces import IFormDefinition, IFieldGroup
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE


class DefinitionBase(SignatureSchemaContext):
    """Base implementation class for form definitions, groups"""
    
    def __init__(self, content_base):
        self.content_base = content_base
        SignatureSchemaContext.__init__(self) #sets self.signature=None
        self.signature_history = PersistentList()
    
    def schema_version(self, signature):
        signature = str(signature.strip())
        if signature not in self.signature_history:
            return -1
        return self.signature_history.index(signature) + 1 #one-indexed
    
    def __getattr__(self, name):
        """Hack to get acquisition and Python property self.schema to work"""
        if name == 'schema':
            return self.__class__.schema.__get__(self)
        # fall back to base class(es) __getattr__ from DexterityContent
        return self.content_base.__getattr__(self, name)
     
    def __getitem__(self, name):
        """low-tech traversal hook"""
        if name == 'edit_schema':
            title = u'Form schema: %s' % self.title
            temp_schema = copy_schema(self.schema) # edit copy, not in-place!
            schema_context = SchemaContext(
                temp_schema, self.REQUEST, name, title).__of__(self)
            return schema_context
        return self.content_base.__getitem__(self, name)


class FormDefinition(Container, DefinitionBase):
    """
    Manages schema for use by form instances.
    
    Form definition is a folderish content item inside a form
    library, may contain other items related to and refining
    the form definition above and beyond the schema.
    """
    
    portal_type = DEFINITION_TYPE
    
    implements(IFormDefinition)
    
    def __init__(self, id=None, *args, **kwargs):
        Container.__init__(self, id, *args, **kwargs)
        DefinitionBase.__init__(self, content_base=Container)


class FieldGroup(Item, DefinitionBase):
    """
    Content type implementation class for field group, which is
    a type of schema provider that lives inside a form definition
    container.
    """
    
    portal_type = FIELD_GROUP_TYPE
    
    implements(IFieldGroup)
    
    def __init__(self, id=None, *args, **kwargs):
        Item.__init__(self, id, *args, **kwargs)
        DefinitionBase.__init__(self, content_base=Item)

