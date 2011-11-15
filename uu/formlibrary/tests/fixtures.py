# module for test fixture construction -- anything that takes part within 
# one or more test cases, for all else, build your common fixtures in the
# layer(s) (see layers.py), not the test cases.


class CreateContentFixtures(object):
    """
    Adapts a test case and plone.app.testing test layer to create
    fixtures as part of a content creation test.  These fixtures 
    may be reused by other test cases using the same layer.
    
    self.context is TestCase.
    self.layer is plone.app.testing test layer.
    self.portal is portal, set from layer.
    
    self.layer.fixtures_completed is flag to ensure content is created
    only once per fixture (shared state for any all instances of 
    CreateContentFixtures and all cases using it).
    
    Call create() method to create content fixtures -- can be called by
    more than one test case, but will only create fixtures once.
    """
    
    def __init__(self, context, layer):
        self.context = context # test case
        self.layer = layer
        self.portal = self.layer['portal']
        self.layer.fixtures_completed = False # self.create() acts only once
     
    def _add_check(self, typename, id, iface, cls, title=None, parent=None):
        if parent is None:
            parent = self.portal
        if title is None:
            title = id
        if isinstance(title, str):
            title = title.decode('utf-8')
        parent.invokeFactory(typename, id, title=title)
        self.context.assertTrue(id in parent.contentIds())
        o = parent[id]
        self.context.assertTrue(isinstance(o, cls))
        self.context.assertTrue(iface.providedBy(o))
        o.reindexObject()
        return o # return constructed content for use in additional testing
    
    def create(self):
        if self.layer.fixtures_completed:
            return # run once, already run
        from uu.formlibrary import (
            interfaces,
            library,
            definition,
            forms,
            formsets,
            )
        library = self._add_check(
            typename=interfaces.LIBRARY_TYPE,
            id='formlib',
            iface=interfaces.IFormLibrary,
            cls=library.FormLibrary,
            parent=self.portal,
            )
        defn = self._add_check(
            typename=interfaces.DEFINITION_TYPE,
            id='def',
            iface=interfaces.IFormDefinition,
            cls=definition.FormDefinition,
            parent=library,
            )
        field_group_a = self._add_check(
            typename=interfaces.FIELD_GROUP_TYPE,
            id='field_group_a',
            iface=interfaces.IFieldGroup,
            cls=definition.FieldGroup,
            title=u'Field group A',
            parent=defn,
            )
        field_group_b = self._add_check(
            typename=interfaces.FIELD_GROUP_TYPE,
            id='field_group_b',
            iface=interfaces.IFieldGroup,
            cls=definition.FieldGroup,
            title=u'Field group B',
            parent=defn,
            )
        setspec = self._add_check(
            typename=interfaces.FORM_SET_TYPE,
            id='form_set_query',
            iface=interfaces.IFormQuery,
            cls=formsets.FormSetSpecifier,
            title=u'Form Set Query',
            parent=defn,
            )
        simple_form = self._add_check(
            typename=interfaces.SIMPLE_FORM_TYPE,
            id='simple',
            iface=interfaces.ISimpleForm,
            cls=forms.SimpleForm,
            parent=self.portal,
            )
        multi_form = self._add_check(
            typename=interfaces.MULTI_FORM_TYPE,
            id='multi',
            iface=interfaces.IMultiForm,
            cls=forms.MultiForm,
            parent=self.portal,
            )
        self.fixtures_completed = True # run once

