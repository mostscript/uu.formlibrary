import unittest2 as unittest
from plone.registry.interfaces import IRegistry
from plone.app.testing import TEST_USER_ID, setRoles

from uu.formlibrary.tests.layers import DEFAULT_PROFILE_TESTING


class DefaultProfileTest(unittest.TestCase):
    """Test default profile's installed configuration settings"""

    layer = DEFAULT_PROFILE_TESTING
    
    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
    
    def test_browserlayer(self):
        """Test product layer interface is registered for site"""
        from uu.formlibrary.interfaces import IFormLibraryProductLayer
        from plone.browserlayer.utils import registered_layers
        self.assertTrue(IFormLibraryProductLayer in registered_layers())

