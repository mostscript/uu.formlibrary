from five import grok
from zope.globalrequest import getRequest
from zope.schema import getFieldsInOrder
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary
from zope.schema.interfaces import IContextSourceBinder

from uu.formlibrary.interfaces import IFormDefinition

from interfaces import IFormComponents


def find_context(request):
    """Find the context from the request; from http://goo.gl/h9d9N"""
    published = request.get('PUBLISHED', None)
    context = getattr(published, '__parent__', None)
    if context is None:
        context = request.PARENTS[0]
    return context


def definition_field_list(context):
    """Flattened list of fieldset/field possibilities for a form definition"""
    base_schema = context.schema
    result = list([
        (name, field.title) for name, field in getFieldsInOrder(base_schema)
        ])
    groups = IFormComponents(context).groups.items()
    for groupid, group in groups:
        schema = group.schema
        group_title = group.Title().decode('utf-8')
        _fieldid = lambda name: '/'.join((groupid, name))
        _title = lambda field: u'[%s] %s' % (group_title, field.title)
        _info = lambda name, field: (_fieldid(name), _title(field))
        result += [_info(name, field)
                   for name, field in getFieldsInOrder(schema)]
    return result


@grok.provider(IContextSourceBinder)
def definition_field_source(context):
    if isinstance(context, dict):
        context = find_context(getRequest())
    definition = IFormDefinition(context)
    unspecified = SimpleTerm(
        value='',
        title=u'Unused / no field specified',
        )
    return SimpleVocabulary(
        [unspecified] + [
            SimpleTerm(value, title=title) for value, title in
            definition_field_list(definition)
        ])

