from zope.interface import implements
from plone.dexterity.content import Container
from plone.schemaeditor.browser.schema.traversal import SchemaContext

from uu.dynamicschema.schema import SignatureSchemaContext

from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.interfaces import DEFINITION_TYPE


class FormDefinition(Container, SignatureSchemaContext):
    """
    Manages schema for use by form instances.
    
    Form definition is a folderish content item inside a form
    library, may contain other items related to and refining
    the form definition above and beyond the schema.
    """
    
    portal_type = DEFINITION_TYPE
    
    implements(IFormDefinition)
    
    def __init__(self, id, *args, **kwargs):
        SignatureSchemaContext.__init__(self) #sets self.signature=None
        Container.__init__(self, id, *args, **kwargs)
    
    def __getattr__(self, name):
        """Hack to get acquisition and Python property self.schema to work"""
        if name == 'schema':
            return self.__class__.schema.__get__(self)
        # fall back to base class(es) __getattr__ from DexterityContent
        return super(FormDefinition, self).__getattr__(name)
     
    def __getitem__(self, name):
        """low-tech traversal hook"""
        if name == 'edit_schema':
            title = u'Form schema: %s' % self.title
            temp_schema = copy_schema(self.schema) # edit copy, not in-place!
            schema_context = SchemaContext(
                temp_schema, self.REQUEST, name, title).__of__(self)
            return schema_context
        return super(FormDefinition, self).__getitem__(name)

