# custom field types

from plone.schemaeditor.fields import FieldFactory
import plone.supermodel.exportimport
from zope.interface import implements
from zope.schema import Field
from zope.schema.interfaces import IField, IFromUnicode


class IDescriptiveText(IField):
    """Descriptive text field"""


class DescriptiveText(Field):
    """Read-only field of descriptive text"""
    implements(IDescriptiveText, IFromUnicode)

    def validate(self, value):
        pass

    def get(self, obj):
        return '1'

    def query(self, obj):
        return '1'

    def set(self, obj, v):
        pass

    def fromUnicode(self, str):
        return '1'


DescriptiveTextFactory = FieldFactory(
    DescriptiveText,
    u'Descriptive Text Label (read-only)',
    required=False,
    )


DescriptiveTextHandler = plone.supermodel.exportimport.BaseHandler(
    DescriptiveText
    )

