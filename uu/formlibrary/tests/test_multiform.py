import doctest
import unittest2 as unittest

from plone.testing import layered
from plone.app.testing import TEST_USER_ID, setRoles

from uu.formlibrary.tests.layers import DEFAULT_PROFILE_TESTING


class MultiFormTest(unittest.TestCase):
    """Test MultiForm implementation"""

    layer = DEFAULT_PROFILE_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.makeSuite(MultiFormTest),
        layered(
            doctest.DocTestSuite('uu.formlibrary.forms'),
            layer=DEFAULT_PROFILE_TESTING,
            ),
        ])
    return suite

