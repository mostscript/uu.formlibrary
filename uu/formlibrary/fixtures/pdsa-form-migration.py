import logging
import os
import sys

from Acquisition import aq_base
from plone.app.textfield.value import RichTextValue
from plone.dexterity.utils import createContent
from plone.uuid.interfaces import IUUID
import transaction
from zope.component import queryUtility
from zope.component.hooks import setSite, getSite
from zope.event import notify
from zope.lifecycleevent import ObjectCopiedEvent

from uu.dynamicschema.interfaces import ISchemaSaver
from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.handlers import definition_schema_handler
from uu.formlibrary.record import FormEntry


OLD_PDSA = 'uu.qiforms.progressform'
LIBTYPE = 'uu.formlibrary.library'
PROJECT_TYPE = 'qiproject'
ZEXP_PATH = 'src/uu.formlibrary/uu/formlibrary/fixtures'
ZEXP = os.path.join(ZEXP_PATH, 'classic-pdsa-progress-form.zexp')
SITES = ('qiteamspace', 'cnhnqi')


FIELDMAP = {
    # assessment field group:
    'rating': ('assessment', 'rating'),
    'meetings': ('assessment', 'meetings'),
    'huddles': ('assessment', 'huddles'),
    'progress_factors': ('assessment', 'progress_factors'),
    'follow_ups': ('assessment', 'follow_ups'),
    # PDSA field group:
    'plan': ('PDSA', 'plan'),
    'do': ('PDSA', 'do'),
    'study': ('PDSA', 'study'),
    'act': ('PDSA', 'act'),
    # Feedback field group
    'support_needed': ('feedback', 'support_needed'),
    }


def get_logger():
    _logger = logging.getLogger('uu.formlibrary')
    handler = logging.StreamHandler(sys.stdout)
    _logger.addHandler(handler)
    logfile = logging.FileHandler('qiforms-pdsa-removal.log')
    _logger.addHandler(logfile)
    _logger.setLevel(logging.INFO)
    return _logger.info, _logger


# global helper functions:
log, logger = get_logger()


_get = lambda brain: brain._unrestrictedGetObject()


def _catalog(site=None):
    return getSite().portal_catalog


def search_within(context=None, catalog=None, **kwargs):
    catalog = catalog or _catalog()
    base = {}
    if context is not None:
        base.update({
            'path': {
                'query': '/'.join(context.getPhysicalPath()),
                'depth': 12,
                },
            })
    base.update(kwargs)
    return catalog.search(base)


## import/migration functionality:

def import_form_definition(library, catalog=None):
    log('Importing classic PDSA form definition for form library '
        '"%s" in project "%s"' % (
            library.getId(),
            library.__parent__.getId()
            )
        )
    defn_id = 'classic-pdsa-progress-form'
    catalog = catalog or _catalog()
    assert os.path.exists(ZEXP)
    # ObjectManager._importObjectFromFile() is insuffiecient for making
    # copies from ZEXP, so we do this ourselves via ZODB connection API
    defn = library._p_jar.importFile(ZEXP)
    defn._setId(defn_id)
    notify(ObjectCopiedEvent(defn, None))
    library._setObject(defn_id, defn)  # will index content in catalog
    assert defn_id in library.objectIds()
    defn = library[defn_id]  # acquisition wrapping new definition
    log('Validating that definition is indexed.')
    assert len(search_within(library, catalog, getId=defn_id))
    saver = queryUtility(ISchemaSaver)
    assert defn.signature in saver
    for component in defn.objectValues():
        # persist, sync field group schemas
        definition_schema_handler(component, None)
        if getattr(component, 'signature', None):
            assert component.signature in saver
    return defn


def flexform(series, name, title, definition):
    portal_type = 'uu.formlibrary.simpleform'
    defn_uid = IUUID(definition)
    content = createContent(
        portal_type,
        title=title,
        definition=defn_uid,
        )
    content.id = name
    series._setObject(name, content)
    return series._getOb(name)


def make_replacement_form(series, oldform, definition):
    assert IFormDefinition.providedBy(definition)
    formid = oldform.getId()
    log(' Replacing form %s in series %s with Flex form.' % (
        formid,
        series.getId(),
        ))
    log('\t -- removing old form of id %s' % formid)
    series.manage_delObjects([formid])
    newform = flexform(series, formid, oldform.Title(), definition)
    newform.start = oldform.start
    newform.end = oldform.end
    log('\t -- created new form with id %s' % newform.getId())
    assert newform.getId() in series.objectIds()
    assert '' in newform.data.keys()    # default fieldset, unused, but...
    newform.data['PDSA'] = FormEntry()  # we need to create other groups
    newform.data['assessment'] = FormEntry()
    newform.data['feedback'] = FormEntry()
    # ...and we must sign each entry:
    for name, group in newform.data.items():
        assert isinstance(group, FormEntry)
        if name == '':
            continue
        group.sign(definition.get(name).schema)
        assert group.signature == definition.get(name).signature
    for sourcename, spec in FIELDMAP.items():
        groupname, fieldname = spec
        group = newform.data.get(groupname, None)
        default = group.schema[fieldname].default
        setattr(group, fieldname, getattr(oldform, sourcename, default))
    newform.reindexObject()
    assert IUUID(definition) == newform.definition
    assert aq_base(IFormDefinition(newform)) is aq_base(definition)


def backup_series(series):
    return  # TODO: don't skip this
    if not os.path.exists('series-backup'):
        os.mkdir('series-backup')
    fname = ':'.join(series.getPhysicalPath())[1:]
    log(' Backing up series: %s' % fname.replace(':', '/'))
    f = open(os.path.join('series-backup', fname), 'w')
    series._p_jar.exportFile(series._p_oid, f)
    f.close()


def create_replacement_forms(oldforms, definition, project):
    archived_series = []
    log('Migrating PDSA forms in project: %s' % project.getId())
    for oldform in oldforms:
        series = oldform.__parent__
        if series not in archived_series:
            backup_series(series)
            archived_series.append(series)
        make_replacement_form(series, oldform, definition)


def fixup_series_contacts(site):
    """
    Some form series have an artifact of previous migration where
    the contact field is stored inappropriate to the schema for the
    series -- stored as unicode instead of as a RichTextValue field.

    This fixes that, which is a pre-condition for migrating items
    contained within (due to link integrity event handlers).
    """
    catalog = site.portal_catalog
    type_query = {'portal_type': 'uu.formlibrary.series'}
    for brain in catalog.search(type_query):
        o = _get(brain)
        if getattr(aq_base(o), 'contact', None):
            if isinstance(o.contact, unicode):
                o.contact = RichTextValue(raw=o.contact.encode('utf-8'))


def pre_migrate(site):
    fixup_series_contacts(site)
    seriesfti = site.portal_types['uu.formlibrary.series']
    seriesfti.allowed_content_types = tuple(
        list(seriesfti.allowed_content_types) + ['uu.qiforms.progressform']
        )


def verify(site):
    assert len(site.portal_catalog.search({'portal_type': OLD_PDSA})) == 0


def post_migrate(site):
    seriesfti = site.portal_types['uu.formlibrary.series']
    # remove appended progressform type from allowed types in series:
    seriesfti.allowed_content_types = seriesfti.allowed_content_types[:-1]


def find_and_migrate(site):
    pre_migrate(site)
    catalog = site.portal_catalog
    projects = [_get(b) for b in catalog.search({'portal_type': 'qiproject'})]
    for project in projects:
        formlib = search_within(project, catalog, portal_type=LIBTYPE)
        result = search_within(project, catalog, portal_type=OLD_PDSA)
        if len(result) and not len(formlib):
            logger.warning(
                'No project form library for old PDSA forms: '
                ' %s' % project.getId()
                )
            continue
        if not len(result):
            continue
        definition = import_form_definition(_get(formlib[0]), catalog)
        oldforms = filter(lambda v: bool(v), map(_get, result))
        create_replacement_forms(oldforms, definition, project)
    post_migrate(site)
    verify(site)


def main(app):
    for name in SITES:
        log('Getting site %s' % name)
        site = app[name]
        setSite(site)
        find_and_migrate(site)
        txn = transaction.get()
        txn.note('/'.join(site.getPhysicalPath()[1:]))
        txn.note('migrated PDSA forms for site %s' % site.getId())
        txn.commit()

if __name__ == '__main__':
    main(app)  # noqa
