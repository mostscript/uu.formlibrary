from plone.uuid.interfaces import IUUID

from collective.computedfield.utils import has_computed_fields
from collective.computedfield.field import complete

from uu.retrieval.catalog import SimpleCatalog
from uu.formlibrary.measure.cache import DataPointCache


def index_records(context):
    context.catalog = SimpleCatalog(context)
    for uid, record in context.items():
        try:
            context.catalog.index(record)
        except TypeError:
            import traceback
            import sys
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, file=sys.stdout)
            print '--------' * 5
            print 'Cound not index record for context: %s' % context
            print 'Record %s' % record.record_uid
            print record.__dict__


def complete_computed_values(context, schema):
    for record in context.values():
        complete(record, schema)


def handle_multiform_modify(context, event):
    """Will add or replace catalog for a multiform"""
    if event and len(getattr(event, 'descriptions', [])):
        if 'items' not in getattr(event.descriptions[0], 'attributes', ()):
            return
    # repoze.catalog indexes for boolean query of records, we want to reset
    # in both cases of empty forms and forms with data:
    index_records(context)
    if len(context):
        # check for computed fields, if any, and computed, if necessary:
        records = context.values()
        schema = records[0].schema
        if has_computed_fields(schema):
            complete_computed_values(context, schema)
    # reload the data point cache for all points/measures for this form:
    DataPointCache().reload(IUUID(context))


def handle_multiform_savedata(context):
    """Hook called from update() of multiform entry view/form"""
    handle_multiform_modify(context, None)  # for now, just replace catalog

