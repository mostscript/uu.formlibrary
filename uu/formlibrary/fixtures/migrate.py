"""
Migration:

* For each project, get the first DIRECTLY contained library.

    * If no library is found, create one in the root of the project
        titled "Form Libray" with id of form-library.

    * If more than one library is found, only use the first found in search.

* Get all form series in project

    * Filter for series only contianing chart audit forms. Skip other series.

    * For each series plus the project-wide library, run the migration function.
"""

import sys
import logging

from plone.uuid.interfaces import IUUID
import transaction
from zope.component import queryUtility
from zope.component.hooks import setSite
from zope.event import notify
from zope.interface.interfaces import IInterface
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent
from zope.schema import getFieldNamesInOrder
from AccessControl.SecurityManagement import newSecurityManager
from Acquisition import aq_parent, aq_inner
from Products.CMFCore.utils import getToolByName

from uu.qiforms.interfaces import IChartAudit
from uu.qiforms.interfaces import IFormSeries as OLDIFormSeries
from uu.formlibrary.interfaces import IMultiForm, IFormDefinition
from uu.formlibrary.interfaces import IFormSeries
from uu.formlibrary.record import FormEntry
from uu.dynamicschema.interfaces import ISchemaSaver


PROJECT_TYPE = 'qiproject'


_logger = logging.getLogger('uu.formlibrary')


_get = lambda b: b._unrestrictedGetObject()


def local_query(context, query, portal_type=None):
    """ 
    Given a catalog search query dict and a context, restrict
    search to items contained in the context path or subfolders.
    """
    path = '/'.join(context.getPhysicalPath())
    query['path'] = { 
        'query' : path,
        }
    if portal_type is not None:
        query['portal_type'] = { 
            'query' : portal_type,
            'operator' : 'or', 
            }
    return query


def migrate_series_schema_to_definition(series, library):
    global _logger
    if not OLDIFormSeries.providedBy(series):
        raise ValueError(
            'series does not provided uu.qiforms.interfaces.IFormSeries'
            )
    new_definition = False
    title_count = len(
        [o for o in library.objectValues()
            if o.Title().startswith('Migrated definition')]
        )
    saver = queryUtility(ISchemaSaver)
    _defn_type = 'uu.formlibrary.definition'
    series_schema_xml = series.entry_schema
    schema_signature = saver.signature(series_schema_xml)
    if schema_signature not in library.objectIds():
        library.invokeFactory(id=schema_signature, type_name=_defn_type)
        definition = library.get(schema_signature)
        definition.title = u'Migrated definition %s' % (title_count + 1)
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


def migrate_series_chartaudit_to_multiforms(source_series, target_series, library):
    global _logger
    _logger.info(
        'Starting migration for series: %s to %s' % (
            '/'.join(source_series.getPhysicalPath()),
            '/'.join(target_series.getPhysicalPath()),
            )
        )
    defn, defn_uid = migrate_series_schema_to_definition(source_series, library)
    _multiform_prefix = 'multi-'
    _multiform_title_suffix = ' (multi-record form)'
    _formtype = 'uu.formlibrary.multiform'
    _is_ca = lambda o: IChartAudit.providedBy(o)
    chartaudit_forms = filter(_is_ca, source_series.objectValues())
    for form in chartaudit_forms:
        formid = form.getId()
        newid = '%s%s' % (_multiform_prefix, formid)
        if newid in target_series.objectIds():
            continue   # already created
        newtitle = '%s%s' % (form.Title(), _multiform_title_suffix)
        target_series.invokeFactory(
            id=newid,
            title=newtitle,
            type_name=_formtype,
            )
        multi = target_series.get(newid)
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
        #multi.reindexObject()  # shoudl be handled by modified event
        _logger.info('Migrated chart audit form %s to lookalike '\
                     ' multi-record form %s -- copied %s records.' % (
                    formid,
                    newid,
                    record_count,
                    )
                )


def get_target_series(series):
    oldid = series.getId()
    newid = '%s-new' % oldid
    parent_folder = aq_parent(aq_inner(series))
    if newid in parent_folder.objectIds():
        series = parent_folder[newid]
        _logger.info('New series found for: %s' % repr(series))
        return series
    parent_folder.invokeFactory(
        id=newid,
        type_name='uu.formlibrary.series',
        )
    new_series = parent_folder[newid]
    copyattrs = getFieldNamesInOrder(IFormSeries)
    for name in copyattrs:
        default = IFormSeries[name].default
        setattr(new_series, name, getattr(series, name, default))
    notify(ObjectCreatedEvent(new_series))  # -> assign UUID
    notify(ObjectModifiedEvent(new_series))
    _logger.info('Created new series: %s based on %s' % (
            repr(series),
            repr(series),
            )
        )
    return new_series


def skip_project(project, catalog):
    global _get
    q1 = local_query(project, {}, 'uu.qiforms.chartaudit')
    q2 = local_query(project, {}, 'uu.qiforms.progressform')
    q3 = local_query(project, {}, 'uu.qiforms.formseries')
    all_chartaudit = map(_get, catalog.search(q1))
    all_progress = map(_get, catalog.search(q2))
    all_oldseries = map(_get, catalog.search(q3))
    return not sum(map(len, (all_chartaudit, all_progress, all_oldseries)))


def migrate_project_forms(project, catalog, delete=False):
    global _get, _logger
    uid_catalog = getToolByName(project, 'uid_catalog')
    _logger.info('Migrate project forms: %s' % project.getId())
    if skip_project(project, catalog):
        _logger.info('Skipping project (no legacy forms): %s' % project.getId())
        return
    libraries = filter(
        lambda o: o.portal_type=='uu.formlibrary.library',
        project.contentValues()
        )
    _lid, _title, _ltype = 'form-library', 'Form library', 'uu.formlibrary.library'
    if _lid in project.contentIds() and project[_lid].portal_type != _ltype:
        _lid = 'form-library-chartaudit'
        _title = 'Form library (chart audit)'
    if not libraries:
        project.invokeFactory(id=_lid, type_name=_ltype, title=_title)
        library = project.get(_lid)
        notify(ObjectCreatedEvent(library))
        library.reindexObject()
        notify(ObjectModifiedEvent(library))
        _logger.info(
            'No library found, created new library %s' % library.getId())
    else:
        library = libraries[0]
        _logger.info('Found library %s' % library.getId())
    q = local_query(project, {}, 'uu.qiforms.formseries')
    all_old_series = map(_get, catalog.search(q))
    _logger.info('Found %s form series in project' % len(all_old_series))
    for series in all_old_series:
        target = get_target_series(series)  # get or make target sibling
        contents = series.contentValues()
        copyids = []
        for o in contents:
            if o.portal_type != 'uu.qiforms.chartaudit':
                copyids.append(o.getId())
        if copyids:
            cp = series.manage_copyObjects(ids=copyids)
            target.manage_pasteObjects(cb_copy_data=cp)
            _logger.info('Copied forms to new series: %s' % repr(copyids))
        ca_contents = filter(
            lambda o: o.portal_type=='uu.qiforms.chartaudit',
            series.contentValues()
            )
        if len(ca_contents) == 0:
            _logger.info(
                'series %s -- no chart audit forms to migrate within' % (
                    series.getId(),
                    )
                )
        else:
            migrate_series_chartaudit_to_multiforms(series, target, library)
        if delete:
            orig_id = series.getId()
            target_id = target.getId()
            old_target_path = '/'.join(target.getPhysicalPath())
            parent = aq_parent(aq_inner(series))
            series_path = '/'.join(series.getPhysicalPath())
            parent.manage_delObjects([orig_id])
            _logger.info('Deleted old form series %s' % series_path)
            parent.manage_renameObject(target_id, orig_id)
            # assert id is changed
            assert target.getId() == orig_id
            assert target_id not in parent.objectIds()
            # fixup for UID catalog after renaming the new series to the
            # old name:
            target_uid = IUUID(target)
            brain = uid_catalog.search(dict(UID=target_uid))[0]
            assert brain.getPath() == old_target_path
            uid_catalog._catalog.uncatalogObject(old_target_path)
            uid_catalog.catalog_object(target, series_path)
            brain = uid_catalog.search(dict(UID=target_uid))[0]
            assert brain.getPath() == series_path
            _logger.info('Renamed new form series to %s' % orig_id)
    q = local_query(project, {}, 'uu.qiforms.formseries')
    assert(len(catalog.search(q)) == 0)  # no remaining old series


def migrate_site_forms(site, delete=False):
    global _get, _logger
    catalog = getToolByName(site, 'portal_catalog')
    projects = map(_get, catalog.search({'portal_type': 'qiproject'}))
    _logger.info('Form migration: found %s projects' % len(projects))
    for project in projects:
        migrate_project_forms(project, catalog, delete)
        sp = transaction.savepoint()


def site_config_migration(site):
    profile_formlibrary = 'profile-uu.formlibrary:default'
    profile_chart = 'profile-uu.chart:default'
    setuptool = getToolByName(site, 'portal_setup')
    setuptool.runImportStepFromProfile(profile_formlibrary, 'typeinfo')
    setuptool.runImportStepFromProfile(profile_chart, 'typeinfo')
    typestool = getToolByName(site, 'portal_types')
    assert 'uu.formlibrary.series' in typestool
    assert 'uu.formlibrary.recordfilter' in typestool
    assert 'uu.formlibrary.measurelibrary' in typestool
    assert 'uu.formlibrary.measuregroup' in typestool
    assert 'uu.chart.data.measureseries' in typestool
    # legacy progress form support, for now:
    if 'uu.qiforms.progressform' in typestool:
        seriesfti = typestool.get('uu.formlibrary.series')
        series_allowed = list(seriesfti.allowed_content_types)
        series_allowed.append('uu.qiforms.progressform')
        seriesfti.allowed_content_types = tuple(sorted(series_allowed))
        assert 'uu.qiforms.progressform' in seriesfti.allowed_content_types
    # qi-specific:
    if 'qiproject' in typestool:
        # Products.qi type fixups:
        #  (1) allow uu.formlibrary.series in qiteam/qisubteam
        #  (2) remove uu.qiforms.formseries from allowed types in qiteam
        #  (3) allow uu.formlibrary.measurelibrary in qiproject
        for name in ('qiteam', 'qisubteam'):
            teamfti = typestool.get(name)
            team_allowed = list(teamfti.allowed_content_types)
            if 'uu.qiforms.formseries' in team_allowed:
                team_allowed.remove('uu.qiforms.formseries')
            team_allowed.append('uu.formlibrary.series')
            teamfti.allowed_content_types = tuple(sorted(team_allowed))
            assert 'uu.qiforms.formseries' not in teamfti.allowed_content_types
            assert 'uu.formlibrary.series' in teamfti.allowed_content_types
        projectfti = typestool.get('qiproject')
        project_allowed = list(projectfti.allowed_content_types)
        project_allowed.append('uu.formlibrary.measurelibrary')
        projectfti.allowed_content_types = tuple(sorted(project_allowed))
        assert 'uu.formlibrary.measurelibrary' in projectfti.allowed_content_types

def migration_wrapper(app, sitename, username='admin', delete=False):
    """
    Sets up site for local components, security context, and transaction
    for running migrate_site_forms().
    """
    global _get, _logger
    handler = logging.StreamHandler(sys.stdout)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    site = app.get(sitename)
    setSite(site)
    _logger.info('Migration started for forms on site: %s' % site)
    user = app.acl_users.getUser(username)
    newSecurityManager(None, user)
    site_config_migration(site)
    migrate_site_forms(site, delete)
    txn = transaction.get()
    txn.note('/'.join(site.getPhysicalPath()[1:]))
    txn.note('Form library migration')
    txn.commit()


if 'app' in locals():
    sitename = 'qiteamspace'
    if len(sys.argv) > 1:
        sitename = sys.argv[1]
        delete = 'delete' in sys.argv
    migration_wrapper(app, sitename, delete=delete)

