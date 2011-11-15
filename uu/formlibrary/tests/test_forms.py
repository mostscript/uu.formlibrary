import unittest2 as unittest

from collective.z3cform.datagridfield.row import DictRow
from plone.registry.interfaces import IRegistry
from plone.app.testing import TEST_USER_ID, setRoles
from Products.CMFPlone.utils import getToolByName
from zope.component import queryUtility
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldNamesInOrder, getFieldsInOrder
import zope.schema

from uu.formlibrary.tests.layers import DEFAULT_PROFILE_TESTING
from uu.formlibrary.tests import test_request


DEFINITION_SCHEMA = """
<model xmlns="http://namespaces.plone.org/supermodel/schema">
  <schema>
    <field name="title" type="zope.schema.TextLine">
      <description>Title of item</description>
      <title>Title</title>
    </field>
    <field name="description" type="zope.schema.Text">
      <description>Describe item.</description>
      <required>False</required>
      <title>Description</title>
    </field>
  </schema>
</model>
""".strip()

GROUP_A_GRID_SCHEMA = """
<model xmlns="http://namespaces.plone.org/supermodel/schema">
  <schema>
    <field name="name" type="zope.schema.TextLine">
      <description>Name</description>
      <title>Name</title>
    </field>
    <field name="number" type="zope.schema.Int">
      <description>Number.</description>
      <required>False</required>
      <title>Number</title>
    </field>
  </schema>
</model>
""".strip()


GROUP_B_FIELDSET_SCHEMA = """
<model xmlns="http://namespaces.plone.org/supermodel/schema">
  <schema>
    <field name="feedback" type="zope.schema.Text">
      <description>Feedback needed?</description>
      <title>Feedback.</title>
    </field>
  </schema>
</model>
""".strip()


class ComposedFormTest(unittest.TestCase):
    """Test ComposedForm adapter (merged form / auto-form)"""

    layer = DEFAULT_PROFILE_TESTING
    
    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.type_fixtures_created = False
    
    def _add_check(self, typename, id, iface, cls, title=None, parent=None):
        if parent is None:
            parent = self.portal
        if title is None:
            title = id
        if isinstance(title, str):
            title = title.decode('utf-8')
        parent.invokeFactory(typename, id, title=title)
        self.assertTrue(id in parent.contentIds())
        o = parent[id]
        self.assertTrue(isinstance(o, cls))
        self.assertTrue(iface.providedBy(o))
        o.reindexObject()
        return o # return constructed content for use in additional testing

    def _fixtures(self):
        from uu.formlibrary.tests.fixtures import CreateContentFixtures
        CreateContentFixtures(self, self.layer).create()
        assert 'formlib' in self.portal.contentIds()
        request = test_request()
        library = self.portal['formlib']
        definition = library['def']
        group_a = definition['field_group_a']
        # MAKE group_a a grid!
        group_a.group_usage = u'grid'
        group_b = definition['field_group_b']
        return (request, library, definition, group_a, group_b)
    
    def test_composed_no_schema(self):
        request, library, definition, group_a, group_b = self._fixtures()
        contained = definition.contentValues()
        assert group_a in contained
        assert group_b in contained
        from uu.formlibrary.forms import ComposedForm
        composed_prior_to_schema = ComposedForm(definition, request)
        composed_prior_to_schema.updateFields()
        # it isn't that there is no schema, it is that the schema is the
        # empty default.
        assert definition.schema is composed_prior_to_schema.schema
        # group A schema is a grid, should not be in additionalSchemata:
        assert group_a.schema not in composed_prior_to_schema.additionalSchemata
        # group B schema is not a grid, but direct fieldset-like construct, 
        # therefore should be in additionalSchemata
        assert group_b.schema in composed_prior_to_schema.additionalSchemata
        assert len(composed_prior_to_schema.additionalSchemata) == 2
    
    def test_prefixes(self):
        request, library, definition, group_a, group_b = self._fixtures()
        from uu.formlibrary.forms import ComposedForm
        composed = ComposedForm(definition, request)
        composed.updateFields()
        assert composed.getPrefix(group_b.schema) == group_b.getId() 
        assert composed.getPrefix(definition.schema) == ''
        # group_a is a special case, it is a grid, so its schema is wrapped
        # in another schema -- indirectly part of form composition:
        assert composed.getPrefix(group_a.schema) != group_a.getId()
        # however:
        from uu.formlibrary.forms import is_grid_wrapper_schema
        schemas = composed.components.values()
        wrapper = [s for s in schemas if is_grid_wrapper_schema(s)][0]
        assert composed.getPrefix(wrapper) == group_a.getId()
    
    def test_composed(self):
        request, library, definition, group_a, group_b = self._fixtures()
        # modify schema (via XML of definition, group) entries, trigger 
        # load of dynamic schema via event handlers from uu.dynamicschema:
        definition.entry_schema = DEFINITION_SCHEMA
        notify(ObjectModifiedEvent(definition))
        assert 'title' in getFieldNamesInOrder(definition.schema)
        group_a.entry_schema = GROUP_A_GRID_SCHEMA
        notify(ObjectModifiedEvent(group_a))
        assert 'name' in getFieldNamesInOrder(group_a.schema)
        group_b.entry_schema = GROUP_B_FIELDSET_SCHEMA
        notify(ObjectModifiedEvent(group_b))
        assert 'feedback' in getFieldNamesInOrder(group_b.schema)
        
        from uu.formlibrary.forms import ComposedForm
        # assumed: ComposedForm can get out of date when the schema of the
        # adapted item changes.  composed.schema and 
        # composed.additionalSchemata reflect the schema of the definition
        # and its contained groups AT THE TIME OF CONSTRUCTION/ADAPTATION
        # -- if this becomes a problem, adjust the property implementation
        # to be a true proxy at a later date, and adjust this test 
        # accordingly.
        composed = ComposedForm(definition, request)
        assert len(composed.additionalSchemata) == 2
        #composed.updateFields()
        composed.update()
        
        # group_a is a grid, which has its schema wrapped by ComposedForm
        # construction -- the wrapper is referenced, we want to get it:
        from uu.formlibrary.forms import is_grid_wrapper_schema
        schemas = composed.components.values()
        wrapper = [s for s in schemas if is_grid_wrapper_schema(s)][0]
        # 'data' is field name for wrapped datagrid as list of DictRow objects
        assert 'data' in wrapper
        assert isinstance(wrapper['data'], zope.schema.List)
        assert isinstance(wrapper['data'].value_type, DictRow)
        column_schema = wrapper['data'].value_type.schema
        assert column_schema == group_a.schema
        
        # with regard to wrapping, serializations for the wrapper are NOT
        # stored or available in the uu.dynamicschema.schema.generated module
        # as they are throw-away and temporary for the scope of one view
        # transaction.  Every time you adapt a definition with ComposedForm, 
        # a new wrapper schema will be created.
        # However, it should be noted that the wrapped schema providing the 
        # field group's columns is persisted in the schema saver:
        from uu.dynamicschema.interfaces import ISchemaSaver
        saver = queryUtility(ISchemaSaver)
        assert saver is not None
        group_signature = saver.signature(group_a.schema)
        # consequence of schema mod above; group_a.schema saved, serialized:
        assert group_signature in saver.keys()
        group_schema_identifier = 'I%s' % group_signature
        from uu.dynamicschema.schema import generated
        #assert group_schema_identifier in generated.__dict__
        dynamic = getattr(generated, group_schema_identifier, None)
        assert dynamic is not None
        assert dynamic is group_a.schema
        
        wrapper_signature = saver.signature(wrapper)
        assert wrapper_signature not in saver.keys() # throw-away not stored
        
        # default fieldset fields:
        composed_schema_fields = [f.field for f in composed.fields.values()]
        assert definition.schema in [
            field.interface for field in composed_schema_fields]
        for name, field in getFieldsInOrder(definition.schema):
            assert name in composed.fields #keys
            assert field in composed_schema_fields
        
        # each field group
        for group in (group_a, group_b):
            schema = group.schema
            if group.group_usage == 'grid':
                schema = wrapper # shortcut, we only have one grid in tests...
                assert schema['data'].required == False
            formgroup = [g for g in composed.groups
                if g.__name__ == group.getId()][0]
            assert schema in [
                field.field.interface for field in formgroup.fields.values()]
            for name, field in getFieldsInOrder(schema):
                fullname = '.'.join((composed.getPrefix(schema), name))
                assert fullname in formgroup.fields # prefixed name in keys
                assert field in [f.field for f in formgroup.fields.values()]
        
        #import pdb; pdb.set_trace() #exploratory TODO TODO TODO REMOVE TODO

