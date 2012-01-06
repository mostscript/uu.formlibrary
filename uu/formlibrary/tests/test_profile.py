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
    
    def _product_fti_names(self):
        from uu.formlibrary import interfaces
        return (
            interfaces.DEFINITION_TYPE,
            interfaces.LIBRARY_TYPE, 
            interfaces.SIMPLE_FORM_TYPE,
            interfaces.MULTI_FORM_TYPE,
            interfaces.FIELD_GROUP_TYPE,
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
   
    def test_creation(self):
        from uu.formlibrary.tests.fixtures import CreateContentFixtures
        CreateContentFixtures(self, self.layer).create()
    
    def _fixtures(self):
        self.test_creation() # set
        assert 'formlib' in self.portal.contentIds()
    
    def test_uuids(self):
        self._fixtures()
        library = self.portal['formlib']
        from plone.uuid.interfaces import IUUID
        self.assertTrue(IUUID(library) is not None)


