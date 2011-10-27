import unittest2 as unittest


class PkgTest(unittest.TestCase):
    """basic unit tests for package go here"""
    
    def test_pkg_import(self):
        """test package import, looks like zcml-initialized zope2 product"""
        import uu.formlibrary
        from uu.formlibrary.zope2 import initialize

