from plone.schemaeditor.browser.schema.listing import SchemaListing
from plone.z3cform.layout import FormWrapper
from Products.CMFCore.utils import getToolByName
from zope.component.hooks import getSite

from uu.formlibrary.interfaces import IFieldGroup
from uu.formlibrary.browser.definition import DefinitionCommon
from uu.formlibrary.forms import common_widget_updates


class ContextSchemaListing(SchemaListing):

    ignoreContext = True

    @property
    def additionalSchemata(self):
        return ()

    def updateWidgets(self):
        common_widget_updates(self)
        super(ContextSchemaListing, self).updateWidgets()

    def __init__(self, context, request):
        super(ContextSchemaListing, self).__init__(context, request)


class FieldSchemaEditor(FormWrapper, DefinitionCommon):
    """View wrapping schema editor from plone.schemaeditor"""

    form = ContextSchemaListing

    # definition tabs relative to schema context
    DEFINITION_TABS = (
        ('Overview', '../@@form_view'),
        ('Field schema', '@@fields'),
        ('Field rules', '../@@fieldrules'),
        )

    # tabs for field group relative to schema editor url:
    GROUP_TABS = (
        ('Group preview', '../@@group_preview'),
        ('Field schema', '@@fields'),
        )

    label = 'Field schema'

    @property
    def catalog(self):
        return getToolByName(getSite(), 'portal_catalog')

    def tabs(self):
        if IFieldGroup.providedBy(self.context.__parent__):
            return self.GROUP_TABS
        return self.DEFINITION_TABS
