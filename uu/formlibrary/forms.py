from zope.interface import implements
from plone.dexterity.content import Item

from uu.record.base import RecordContainer
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE


class SimpleForm(Item):
    """
    Single-record form instance tied to a specific form definition and its
    schema.
    """
   
    portal_type = SIMPLE_FORM_TYPE

    implements(ISimpleForm)


class MultiForm(Item, RecordContainer):
    """
    Multi-record form instance tied to a specific form definition and its
    schema.  Acts as a record container.
    """
   
    portal_type = MULTI_FORM_TYPE

    implements(IMultiForm)


