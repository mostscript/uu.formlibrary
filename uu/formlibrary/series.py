from plone.dexterity.content import Container
from zope.interface import implements

from uu.formlibrary.interfaces import IFormSeries, SERIES_TYPE


class FormSeries(Container):
    implements(IFormSeries)
    portal_type = SERIES_TYPE

