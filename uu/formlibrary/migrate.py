import logging

from plone.uuid.interfaces import IUUID
from zope.component import queryUtility
from zope.event import notify
from zope.interface.interfaces import IInterface
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent
from zope.schema import getFieldNamesInOrder

from uu.qiforms.interfaces import IFormSeries, IChartAudit
from uu.formlibrary.interfaces import IMultiForm, IFormDefinition
from uu.formlibrary.record import FormEntry
from uu.dynamicschema.interfaces import ISchemaSaver


_logger = logging.getLogger('uu.formlibrary')


def migrate_series_schema_to_definition(series, library):
    global _logger
    if not IFormSeries.providedBy(series):
        raise ValueError(
            'series does not provided uu.qiforms.interfaces.IFormSeries'
            )
    new_definition = False
    saver = queryUtility(ISchemaSaver)
    _defn_type = 'uu.formlibrary.definition'
    series_schema_xml = series.entry_schema
    schema_signature = saver.signature(series_schema_xml)
    if schema_signature not in library.objectIds():
        library.invokeFactory(id=schema_signature, type_name=_defn_type)
        definition = library.get(schema_signature)
        notify(ObjectCreatedEvent(definition))  # will create UUID
        new_definition = True
    definition = library.get(schema_signature)
    defn_uid = IUUID(definition, None)
    assert defn_uid is not None
    if new_definition:
        definition.entry_schema = series_schema_xml
        notify(ObjectModifiedEvent(definition))  # will sync xml -> schema
        assert IInterface.providedBy(definition.schema)
    defn_uid = IUUID(definition)
    definition.reindexObject()
    _logger.info(
        'Created definition with signature %s and UID: %s' % (
            schema_signature,
            defn_uid,
            )
        )
    return definition, defn_uid


def migrate_series_chartaudit_to_multiforms(series, library):
    global _logger
    defn, defn_uid = migrate_series_schema_to_definition(series, library)
    _multiform_prefix = 'multi-'
    _multiform_title_suffix = ' (multi-record form)'
    _formtype = 'uu.formlibrary.multiform'
    _is_ca = lambda o: IChartAudit.providedBy(o)
    chartaudit_forms = filter(_is_ca, series.objectValues())
    for form in chartaudit_forms:
        formid = form.getId()
        newid = '%s%s' % (_multiform_prefix, formid)
        if newid in series.objectIds():
            continue   # already created
        newtitle = '%s%s' % (form.Title(), _multiform_title_suffix)
        series.invokeFactory(id=newid, title=newtitle, type_name=_formtype)
        multi = series.get(newid)
        notify(ObjectCreatedEvent(multi))
        assert IUUID(multi, None) is not None
        # bind form definition:
        multi.definition = defn_uid
        # copy attributes from chart audit
        for attrname in ('title', 'start', 'end', 'notes'):
            default = IMultiForm[attrname].default or None
            v = getattr(form, attrname, default)
            setattr(multi, attrname, v)
        # process_changes attribute, if non-empty, to entry_notes on new form
        entry_notes = getattr(form, 'process_changes', None)
        if entry_notes:
            multi.entry_notes = entry_notes.strip()
        # finally, copy record data:
        for uid, record in form.items():
            assert record.record_uid == uid
            newrec = FormEntry(multi, uid)
            for fieldname in getFieldNamesInOrder(defn.schema):
                if fieldname != 'record_uid' and fieldname in record.__dict__:
                    setattr(newrec, fieldname, getattr(record, fieldname))
            multi.add(newrec)
        # lastly, notify object modified event:
        notify(ObjectModifiedEvent(multi))
        record_count = len(multi)
        assert len(multi) == len(form)  # same number of items
        assert multi.keys() == form.keys()  # same order of records
        multi.reindexObject()
        _logger.info('Migrated chart audit form %s to lookalike '\
                     ' multi-record form %s -- copied %s records.' % (
                    formid,
                    newid,
                    record_count,
                    )
                )


