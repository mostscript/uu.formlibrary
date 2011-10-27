import unittest2 as unittest

from plone.registry.interfaces import IRegistry
from plone.app.testing import TEST_USER_ID, setRoles
from Products.CMFPlone.utils import getToolByName

from uu.formlibrary.tests.layers import DEFAULT_PROFILE_TESTING


class DefaultProfileTest(unittest.TestCase):
    """Test default profile's installed configuration settings"""

    layer = DEFAULT_PROFILE_TESTING
    
    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.type_fixtures_created = False
    
    def _product_fti_names(self):
        from uu.formlibrary import interfaces
        return (
            interfaces.DEFINITION_TYPE,
            interfaces.LIBRARY_TYPE, 
            interfaces.SIMPLE_FORM_TYPE,
            interfaces.MULTI_FORM_TYPE,
            interfaces.FORM_SET_TYPE,
            )

    def test_browserlayer(self):
        """Test product layer interface is registered for site"""
        from uu.formlibrary.interfaces import IFormLibraryProductLayer
        from plone.browserlayer.utils import registered_layers
        self.assertTrue(IFormLibraryProductLayer in registered_layers())
    
    def test_ftis(self):
        types_tool = getToolByName(self.portal, 'portal_types')
        typenames = types_tool.objectIds()
        for name in self._product_fti_names():
            self.assertTrue(name in typenames)
   
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
    
    def test_creation(self):
        if self.type_fixtures_created:
            return # already run
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
        definition = self._add_check(
            typename=interfaces.DEFINITION_TYPE,
            id='def',
            iface=interfaces.IFormDefinition,
            cls=definition.FormDefinition,
            parent=library,
            )
        setspec = self._add_check(
            typename=interfaces.FORM_SET_TYPE,
            id='form_set_query',
            iface=interfaces.IFormQuery,
            cls=formsets.FormSetSpecifier,
            title=u'Form Set Query',
            parent=definition,
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
        self.type_fixtures_created = True
    
    def _fixtures(self):
        if not self.type_fixtures_created:
            self.test_creation() # set
        assert 'formlib' in self.portal.contentIds()
    
    def test_uuids(self):
        self._fixtures()
        library = self.portal['formlib']
        from plone.uuid.interfaces import IUUID
        self.assertTrue(IUUID(library) is not None)


