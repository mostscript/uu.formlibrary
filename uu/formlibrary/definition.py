from datetime import datetime

from persistent import Persistent
from persistent.list import PersistentList
from plone.dexterity.content import Container, Item, DexterityContent
from plone.schemaeditor.browser.schema.traversal import SchemaContext
from zope.component import adapts
from zope.interface import implements

from uu.dynamicschema.schema import SignatureSchemaContext
from uu.dynamicschema.schema import copy_schema

from uu.formlibrary.interfaces import IFormDefinition, IFieldGroup
from uu.formlibrary.interfaces import DEFINITION_TYPE, FIELD_GROUP_TYPE
from uu.formlibrary.interfaces import IDefinitionHistory, IFormComponents


itemkeys = lambda seq: zip(*seq)[0] if seq else []  # unzip items tuple
is_field_group = lambda o: o.portal_type == FIELD_GROUP_TYPE


class DefinitionHistory(Persistent):
    """Definition history metadata (log entry) provides IDefinitionHistory"""
    
    implements(IDefinitionHistory)
    
    def __init__(self, context, *args, **kwargs):
        if not IFormDefinition.providedBy(context):
            raise ValueError('context must provide IFormDefinition')
        self.context = context  # form definition
        self.namespace = kwargs.get('namespace', '')
        self.signature = kwargs.get('signature', None)
        self.modified = kwargs.get('modified', datetime.now())
        self.modification = kwargs.get('modification', 'modified')
        self.note = kwargs.get('note', None)


class FormComponents(object):
    """Adapter implementation for IFormComponents"""
    
    implements(IFormComponents)
    adapts(IFormDefinition)
    
    def __init__(self, context):
        self.context = context
        self._load_items()
    
    def _load_items(self):
        self._items = [(name, o) for name, o in self.context.objectItems()
                       if is_field_group(o)]
    
    @property
    def names(self):
        return tuple(itemkeys(self._items))
    
    @property
    def groups(self):
        return dict(self._items)


class DefinitionBase(SignatureSchemaContext):
    """Base implementation class for form definitions, groups"""
    
    def __init__(self, content_base):
        self.content_base = content_base
        SignatureSchemaContext.__init__(self)  # sets self.signature=None
        self.signature_history = PersistentList()
    
    def schema_version(self, signature):
        signature = str(signature.strip())
        if signature not in self.signature_history:
            return -1
        return self.signature_history.index(signature) + 1  # one-indexed
    
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
            temp_schema = copy_schema(self.schema)  # edit copy, not in-place!
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
        self.definition_history = PersistentList()
    
    def __getitem__(self, name):
        if name in self.objectIds():
            return Container.__getitem__(self, name)
        return DefinitionBase.__getitem__(self, name)  # traversal hook
    
    def log(self, *args, **kwargs):
        if not hasattr(self, 'definition_history'):
            self.definition_history = PersistentList()
        if len(args) == 1 and IDefinitionHistory.providedBy(args[0]):
            self.definition_history.append(args[0])
            return
        entry = DefinitionHistory(self, **kwargs)
        self.definition_history.append(entry)
    
    # work-around until plone.dexterity 1.0.2 released ( http://goo.gl/w40bc )
    Title = DexterityContent.Title
    setTitle = DexterityContent.setTitle
    Description = DexterityContent.Description
    setDescription = DexterityContent.setDescription


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
    
    # work-around until plone.dexterity 1.0.2 released ( http://goo.gl/w40bc )
    Title = DexterityContent.Title
    setTitle = DexterityContent.setTitle
    Description = DexterityContent.Description
    setDescription = DexterityContent.setDescription


