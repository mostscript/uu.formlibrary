from five import grok
from zope.component import queryAdapter
from zope.globalrequest import getRequest
from zope.schema import getFieldsInOrder
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.interfaces import IField, IFloat, IInt

from uu.formlibrary.interfaces import IFormDefinition

from interfaces import IFormComponents


def find_context(request):
    """Find the context from the request; from http://goo.gl/h9d9N"""
    published = request.get('PUBLISHED', None)
    context = getattr(published, '__parent__', None)
    if context is None:
        context = request.PARENTS[0]
    return context


def field_provides(field, ifaces):
    """Does field provide at least one of the interfaces specified?"""
    _pb = lambda iface: iface.providedBy(field)
    return any(map(_pb, ifaces))


def definition_field_list(context, field_ifaces=(IField,)):
    """Flattened list of fieldset/field possibilities for a form definition"""
    base_schema = context.schema
    result = list([
        (name, field.title) for name, field in getFieldsInOrder(base_schema)
        if field_provides(field, field_ifaces)
        ])
    groups = IFormComponents(context).groups.items()
    for groupid, group in groups:
        schema = group.schema
        group_title = group.Title().decode('utf-8')
        _fieldid = lambda name: '/'.join((groupid, name))
        _title = lambda field: u'[%s] %s' % (group_title, field.title)
        _info = lambda name, field: (_fieldid(name), _title(field))
        result += [_info(name, field)
                   for name, field in getFieldsInOrder(schema)
                   if field_provides(field, field_ifaces)]
    return result


@grok.provider(IContextSourceBinder)
def definition_field_source(context, field_ifaces=(IField,)):
    if isinstance(context, dict):
        context = find_context(getRequest())
    definition = IFormDefinition(context)
    meta_defn = queryAdapter(definition, IFormDefinition, name='metadata')
    if meta_defn is not None:
        definition = meta_defn
    unspecified = SimpleTerm(
        value='',
        title=u'Unused / no field specified',
        )
    return SimpleVocabulary(
        [unspecified] + [
            SimpleTerm(value, title=title) for value, title in
            definition_field_list(definition, field_ifaces)
        ])


@grok.provider(IContextSourceBinder)
def definition_numeric_fields(context):
    return definition_field_source(context, (IInt, IFloat))

