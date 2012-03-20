import unittest2 as unittest

from plone.registry.interfaces import IRegistry
from plone.app.testing import TEST_USER_ID, setRoles
from Products.CMFPlone.utils import getToolByName

from uu.formlibrary.tests.layers import DEFAULT_PROFILE_TESTING


class DefaultProfileTest(unittest.TestCase):
    """Test default profile's installed configuration settings"""

    layer = DEFAULT_PROFILE_TESTING
    
    FOLDERISH_TYPES = [
        'uu.formlibrary.library',
        'uu.formlibrary.definition'
        ]
    
    LINKABLE_TYPES = FOLDERISH_TYPES + [
        'uu.formlibrary.fieldgroup',
        'uu.formlibrary.setspecifier',
        'uu.formlibrary.multiform',
        'uu.formlibrary.simpleform',
        ]
    
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
    
    def test_tinymce_settings(self):
        tool = self.portal.portal_tinymce
        folderish = tool.containsobjects.strip().split('\n')
        linkable = tool.linkable.strip().split('\n')
        ## test for regressions from base profile, defaults still set:
        self.assertTrue(tool.styles)  # non-empty === product does not touch
        base_plone_folders = (
            'Folder', 
            'Large Plone Folder',
            'Plone Site',
            )
        for portal_type in base_plone_folders:
            self.assertIn(portal_type, folderish)
        base_plone_linkable = (
            'Topic',
            'Event',
            'File',
            'Folder', 
            'Large Plone Folder',
            'Image',
            'News Item',
            'Document',
            )
        for portal_type in base_plone_linkable:
            self.assertIn(portal_type, linkable)
        ## now test for resources added by this profile:
        for portal_type in self.FOLDERISH_TYPES:
            self.assertIn(portal_type, folderish)
        for portal_type in self.LINKABLE_TYPES:
            self.assertIn(portal_type, linkable)


