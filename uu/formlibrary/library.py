from zope.interface import implements
from plone.dexterity.content import Container

from uu.formlibrary.interfaces import IFormLibrary
from uu.formlibrary.interfaces import LIBRARY_TYPE


class FormLibrary(Container):
    """
    Form library contains form definitions providing IFormDefinition.
    """

    portal_type = LIBRARY_TYPE

    implements(IFormLibrary)

