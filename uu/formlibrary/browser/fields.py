from plone.schemaeditor.browser.schema.listing import SchemaListing
from plone.z3cform.layout import FormWrapper


# definition tabs relative to schema context
DEFINITION_TABS = (
    ('Overview', '../@@form_view'),
    ('Field schema', '@@fields'),
    ('Field rules', '../@@fieldrules'),
    )


class ContextSchemaListing(SchemaListing):
    
    ignoreContext = True

    @property
    def additionalSchemata(self):
        return ()
    
    def __init__(self, context, request):
        super(ContextSchemaListing, self).__init__(context, request)


class FieldSchemaEditor(FormWrapper):
    """View wrapping schema editor from plone.schemaeditor"""

    form = ContextSchemaListing

    label = 'Field schema'

    tabs = DEFINITION_TABS

