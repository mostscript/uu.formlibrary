from zope.component import queryUtility
from zope.globalrequest import getRequest
from Acquisition import aq_base
from OFS.interfaces import IObjectManager
from Products.CMFCore.utils import getToolByName
from plone.app.linkintegrity.exceptions import (
    LinkIntegrityNotificationException)

from uu.dynamicschema.interfaces import ISchemaSaver
from uu.dynamicschema.interfaces import DEFAULT_MODEL_XML, DEFAULT_SIGNATURE
from uu.formlibrary.interfaces import IDefinitionBase, IFormSet, ISimpleForm
from uu.formlibrary.interfaces import IFormDefinition, IFieldGroup
from uu.formlibrary.interfaces import IFormComponents
from uu.formlibrary.forms import form_definition
from uu.formlibrary.record import FormEntry
from uu.formlibrary.utils import grid_wrapper_schema


def copyroles(source, dest):
    """ 
    recursive copy of local roles for a copied content item or tree thereof.
    """
    local_roles = source.get_local_roles()
    for (userid, roles) in local_roles:
        dest.manage_setLocalRoles(userid, list(roles))
    if IObjectManager.providedBy(source):
        for name, contained in source.objectItems():
            if name in dest.objectIds():
                copyroles(contained, dest[name])


def definition_delete_integrity(context, event):
    request = getRequest()
    if request is not None:
        formset = IFormSet(context)
        if len(formset) > 0:
            msg = 'Item in use, cannot be removed while form instances '\
                  'are using this definition.'
            raise LinkIntegrityNotificationException(msg)


def handle_copypaste_local_roles(context, event):
    """ 
    Event handler for subscriber to object, IObjectCopiedEvent that
    copies explicit (not computed from context) local roles from
    source to destination.
    """
    dest = event.object
    source = event.original
    copyroles(source, dest)


def sync_simple_form(form, components):
    """
    Sync form data storage objects with schema of form definition
    components.
    """
    for name in components.names:
        group = components.groups[name]
        schema = group.schema
        if group.group_usage == u'grid':
            schema = grid_wrapper_schema(group.schema)
        if name not in form.data:
            form.data[name] = FormEntry() # add new
        form.data[name].sign(schema)


def simple_form_configuration_modified(context, event):
    if not ISimpleForm.providedBy(context):
        raise ValueError('context must be ISimpleForm provider')
    ## re-sign context and data-record with current definition/schema:
    try:
        definition = form_definition(context)
    except ValueError:
        return # no definition means no schema to sync
    components = IFormComponents(definition)
    sync_simple_form(context, components)


def update_form_entries(context):
    definition = context
    if IFieldGroup.providedBy(context):
        definition = context.__parent__
    bound_forms = IFormSet(definition)
    simple_forms = [f for f in bound_forms.values()
        if ISimpleForm.providedBy(f)] #TODO: named IFormSet adapter instead???
    wftool = getToolByName(definition, 'portal_workflow')
    components = IFormComponents(definition)
    for form in simple_forms:
        if wftool.getInfoFor(form, 'review_state') == 'visible':
            # only if form is in visible state is it considered okay to
            # modify the schema of records within it.
            for name in components.names:
                group = components.groups[name]
                schema = group.schema
                if group.group_usage == u'grid':
                    schema = grid_wrapper_schema(group.schema)
                if name not in form.data:
                    form.data[name] = FormEntry() # add new
                form.data[name].sign(schema)


def definition_schema_handler(context, event):
    """
    Event handler for object modification parses XML schema definition with 
    plone.supermodel (via local ISchemaSaver utility), then saves:
        
        * context.signature (persistent attribute)
        
        * context._v_schema (convenient caching for current thread)**
        
            **  other threads can load this on-demand, that is left to
                the FormDefinition.schema property implementation.
    
    This handler also normalizes the XML schema string in context.entry_schema
    with context.entry_schema.strip() (just in case it is needed).
    
    Does nothing if entry_schema is absent/empty.
    """
    if context.entry_schema:
        ## serialization fixups and normalization:
        schema = context.entry_schema = context.entry_schema.strip()
        schema = schema.replace('\r','') # remove all CRs
        if (schema == DEFAULT_MODEL_XML and
                context.signature == DEFAULT_SIGNATURE):
            return # initial schema, not modification of schema; done.
        saver = queryUtility(ISchemaSaver)          # get local utility
        sig = context.signature = saver.add(schema) # persist xml/sig in saver
        context._v_schema = (sig, saver.load(saver.get(sig))) # cache schema
        update_form_entries(context)


def reserialize(context, schema):
    if not IDefinitionBase.providedBy(context.__parent__):
        return #not an event we care about
    definition = context.__parent__
    saver = queryUtility(ISchemaSaver)
    new_signature = saver.add(schema)
    new_xml = saver.get(new_signature)
    definition.entry_schema = new_xml
    definition.signature = new_signature
    if IFormDefinition.providedBy(definition):
        update_form_entries(definition)
    # TODO: deal with nested groups and associated data objects contained
    if hasattr(aq_base(definition), '_v_schema'):
        delattr(aq_base(definition), '_v_schema') #invalidate previous schema
    definition.reindexObject()


def serialize_context_schema_changed(context, event):
    reserialize(context, context.schema)

