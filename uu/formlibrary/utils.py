from plone.autoform.interfaces import WIDGETS_KEY
from collective.z3cform.datagridfield import DictRow, DataGridFieldFactory
from zope.schema import List

from uu.dynamicschema.schema import new_schema


WIDGET = 'collective.z3cform.datagridfield.datagridfield.DataGridFieldFactory'

def grid_wrapper_schema(schema, title=u'', description=u''):
    """
    Given a schema interface for use in a data-grid, construct and 
    return a wrapper form interface to use that grid (DictRow).
    """
    # create empty new dynamic schema
    wrapper = new_schema()
    # inject a field into that schema interface
    grid = List(
        title=unicode(title),
        description=unicode(description),
        value_type=DictRow(schema=schema),
        )
    grid.__name__ = 'data'
    grid.interface = wrapper
    grid.required = False # ugly in form UI, widget will render regardless
    wrapper._InterfaceClass__attrs['data'] = grid
    # specify plone.autoform widget config for field:
    wrapper.setTaggedValue(WIDGETS_KEY, {'data' : WIDGET})
    return wrapper

