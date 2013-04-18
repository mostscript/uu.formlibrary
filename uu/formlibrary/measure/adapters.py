from Acquisition import aq_parent, aq_inner
from zope.component import adapter
from zope.component.hooks import getSite
from zope.interface import implements, implementer

from uu.formlibrary.interfaces import IFormDefinition

from interfaces import IMeasureDefinition


@implementer(IFormDefinition)
@adapter(IMeasureDefinition)
def measure_form_definition(context):
    measure_group = aq_parent(aq_inner(context))
    form_definition_uid = measure_group.definition
    if not form_definition_uid:
        return None
    site = getSite()
    catalog = site.portal_catalog
    r = catalog.search({'UID': form_definition_uid})
    if not r:
        return None
    return r[0]._unrestrictedGetObject()

