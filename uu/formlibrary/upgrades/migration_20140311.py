# migration / 2014-03-11

from Acquisition import aq_base
from plone.uuid.interfaces import IUUID, ATTRIBUTE_NAME
import transaction
from zope.component import queryAdapter
from zope.component.hooks import setSite, getSite

from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.search.filters import FieldQuery
from uu.formlibrary.search.interfaces import IComposedQuery
from uu.formlibrary.measure.content import is_query_complete
from uu.formlibrary.measure.cache import DataPointCache
from uu.formlibrary.measure.interfaces import MEASURE_DEFINITION_TYPE

PKGNAME = 'uu.formlibrary'
BASEPATH = '/VirtualHostBase/https/teamspace.upiq.org'


_installed = lambda site: site.portal_quickinstaller.isProductInstalled
product_installed = lambda site, name: _installed(site)(name)

_search = lambda site, q: site.portal_catalog.unrestrictedSearchResults(q)
_get = lambda brain: brain._unrestrictedGetObject()


def premigrate_filter(measure, name):
    """
    Given a measure, get the content-based RecordFilter from
    the _tree, and return the content.
    """
    tree = getattr(aq_base(measure), '_tree', {})
    rfilter = tree.get(name, None)
    if rfilter is not None:
        rfilter = rfilter.__of__(measure)
    return rfilter


def prior_incomplete_measure(measure):
    group = measure.__parent__
    schema = IFormDefinition(measure).schema
    if group.source_type == 'uu.formlibrary.simpleform':
        return False  # ignore SimpleForm-based measures, no queries!
    if measure.numerator_type == 'multi_filter':
        rfilter = premigrate_filter(measure, 'numerator')
        if rfilter is None or not is_query_complete(rfilter.build(schema)):
            return True
    if measure.denominator_type == 'multi_filter':
        rfilter = premigrate_filter(measure, 'denominator')
        if rfilter is None or not is_query_complete(rfilter.build(schema)):
            return True
    return False


def premigrate_incomplete_measures(site):
    """
    Given a site, get all measures, and determine which measures have
    incomplete record filters (prior to migration), given config;
    returns list of UID.
    """
    incomplete = []
    q = {'portal_type': MEASURE_DEFINITION_TYPE}
    measures = map(_get, _search(site, q))
    for measure in measures:
        if prior_incomplete_measure(measure):
            incomplete.append(IUUID(measure))
    return incomplete


def clear_filter(rfilter):
    for k in rfilter.keys():
        del(rfilter[k])


def copy_query(q):
    return FieldQuery(q.fieldname, q.comparator, q.value)


def query_filters(composed):
    """
    Given a composed query, return list of all filters; for
    migration purposes, we only really need first.
    """
    r = []
    for group in composed:
        for rfilter in group:
            r.append(rfilter)
    return r


def copy_filter(source, destination):
    """
    Copy record filter by copying its contained FieldQuery objects.
    """
    clear_filter(destination)
    destination.reset()
    destination.operator = source.operator
    for query in source.values():
        destination.add(copy_query(query))


def verify_filter(source, destination, schema):
    assert is_query_complete(destination.build(schema))
    assert len(source) == len(destination)
    for fieldname in source.keys():
        q1, q2 = source[fieldname], destination[fieldname]
        assert q1.fieldname == q1.fieldname
        assert q1.comparator == q2.comparator
        assert q1.value == q2.value
        assert source.operator == destination.operator


def remove_content_filter(rfilter):
    catalog = getSite().portal_catalog
    if isinstance(rfilter, str):
        uid = rfilter
    else:
        uid = getattr(aq_base(rfilter), ATTRIBUTE_NAME, None)
    r = catalog.unrestrictedSearchResults({'UID': uid})
    if r:
        # have a record, lets get the path
        brain = r[0]
        assert brain.portal_type == 'uu.formlibrary.recordfilter'
        catalog._catalog.uncatalogObject(brain.getPath())


def migrate_filter(measure, queryname):
    schema = IFormDefinition(measure).schema
    rfilter = premigrate_filter(measure, queryname)
    composed = queryAdapter(measure, IComposedQuery, name=queryname)
    destination = query_filters(composed)[0]
    copy_filter(rfilter, destination)
    verify_filter(rfilter, destination, schema)
    remove_content_filter(rfilter)
    

def migrate_measure(measure):
    if prior_incomplete_measure(measure):
        msg = 'IGNORING incomplete measure %s'
        if hasattr(aq_base(measure), '_composed_queries'):
            msg = 'SKIPPING already migrated measure %s'
        print msg % ('/'.join(measure.getPhysicalPath()),)
        return 0
    if measure.numerator_type == 'multi_filter':
        migrate_filter(measure, 'numerator')
    if measure.denominator_type == 'multi_filter':
        migrate_filter(measure, 'denominator')
    # finally, remove _tree storing old contained content (filters):
    if hasattr(aq_base(measure), '_tree'):
        delattr(aq_base(measure), '_tree')
    return 1


def incomplete_cleanups(site):
    catalog = getSite().portal_catalog
    q = {'portal_type': 'uu.formlibrary.recordfilter'}
    while 1:
        r = _search(site, q)
        if not r:
            break
        for brain in r:
            path = brain.getPath()
            measure_path = '/'.join(path.split('/')[:-1])
            catalog._catalog.uncatalogObject(path)
            rmeasure = _search(
                site,
                {'path': {'query': measure_path, 'depth': 0}},
                )
            assert len(rmeasure) == 1
            measure = rmeasure[0]._unrestrictedGetObject()
            if hasattr(aq_base(measure), '_tree'):
                delattr(aq_base(measure), '_tree')


def migrate_measures(site):
    migrated = 0
    all_count = 0
    prior_incomplete = premigrate_incomplete_measures(site)  # UIDs incomplete
    q = {'portal_type': MEASURE_DEFINITION_TYPE}
    for brain in _search(site, q):
        measure = _get(brain)
        group = measure.__parent__
        if group.source_type == 'uu.formlibrary.simpleform':
            continue  # ignore SimpleForm-based measure, no queries to migrate
        migrated += migrate_measure(measure)
        all_count += 1
    print 'Migrated %s measures from legacy RecordFilter(s), of %s' % (
        migrated,
        all_count,
        )
    print 'Cleaning up remaining legacy RecordFilter entries from catalog'
    incomplete_cleanups(site)
    # VERIFY / assertions:
    # 1. NO RecordFilter content cataloged any more:
    q = {'portal_type': 'uu.formlibrary.recordfilter'}
    assert len(_search(site, q)) == 0
    # 2. For all measures, things look good:
    q = {'portal_type': MEASURE_DEFINITION_TYPE}
    for brain in _search(site, q):
        measure = _get(brain)
        schema = IFormDefinition(measure).schema
        group = measure.__parent__
        if group.source_type == 'uu.formlibrary.simpleform':
            continue  # ignore SimpleForm-based measure, no queries to migrate
        # 2.a. NO _tree; since MeasureDefinition
        # is not subclasing plone.dexterity.content.Container any more
        # in favor of Item, we need to directly access tree:
        try:
            assert getattr(aq_base(measure), '_tree', None) is None
        except AssertionError:
            # likely a tree with no filters, so clean up here:
            assert len(aq_base(measure)._tree) == 0
            delattr(aq_base(measure), '_tree')
        # 2.b. IComposedQuery for measure configuration looks okay, for
        # numerator, denominator as configured.
        if group.source_type == 'uu.formlibrary.simpleform':
            continue  # ignore SimpleForm-based measures, no queries!
        else:
            # get whether num, den...
            # build query for each:
            # assert is_query_complete(q.build())
            adapter = lambda name: queryAdapter(measure, IComposedQuery, name)
            if IUUID(measure) not in prior_incomplete:
                if measure.numerator_type == 'multi_filter':
                    composed = adapter(u'numerator')
                    assert is_query_complete(composed.build(schema))
                if measure.denominator_type == 'multi_filter':
                    composed = adapter(u'denominator')
                    assert is_query_complete(composed.build(schema))


def migrate_cachewarm(site):
    cache = DataPointCache(site)
    cache.warm()


def commit(context, msg):
    print msg
    txn = transaction.get()
    # Undo path, if you want to use it, unfortunately is site-specific,
    # so use the hostname used to access all Plone sites.
    # TODO UNCOMMENT BELOW TODO
    assert txn  # TODO noqa remove this
    txn.note('%s%s' % (BASEPATH, '/'.join(context.getPhysicalPath())))
    txn.note(msg)
    txn.commit()


def migrate(site):
    print '\n\n=== For site %s ===\n' % site.getId()
    migrate_measures(site)
    commit(site, 'Migrated measure query filters for %s' % site.getId())
    migrate_cachewarm(site)
    commit(site, 'Warmed data point cache for %s' % site.getId())
    print '*** DONE FOR SITE %s ***' % site.getId()


def main(app):
    for site in app.objectValues('Plone Site'):
        setSite(site)
        if product_installed(site, PKGNAME):
            migrate(site)


if __name__ == '__main__' and 'app' in locals():
    main(app)  # noqa

