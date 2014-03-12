# migration / 2014-03-11

from Acquisition import aq_base
from plone.uuid.interfaces import IUUID
import transaction
from zope.component import queryAdapter
from zope.component.hooks import setSite

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
    rfilter = aq_base(measure)._tree.get(name, None)
    if rfilter is not None:
        rfilter = rfilter.__of__(measure)
    return rfilter


def prior_incomplete_measure(measure):
    group = measure.__parent__
    if group.source_type == 'uu.formlibrary.simpleform':
        return False  # ignore SimpleForm-based measures, no queries!
    if measure.numerator_type == 'multi_filter':
        rfilter = premigrate_filter(measure, 'numerator')
        if rfilter is None or not is_query_complete(rfilter.build()):
            return True
    if measure.denominator_type == 'multi_filter':
        rfilter = premigrate_filter(measure, 'denominator')
        if rfilter is None or not is_query_complete(rfilter.build()):
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


def migrate_measure(measure):
    pass  # TODO


def migrate_measures(site, count=0):
    prior_incomplete = premigrate_incomplete_measures()  # UIDs of incomplete
    q = {'portal_type': MEASURE_DEFINITION_TYPE}
    for brain in _search(site, q):
        migrate_measure(_get(brain))
        count += 1
    print 'Migrated %s measures from legacy RecordFilter' % count
    # VERIFY / assertions:
    # 1. NO RecordFilter content cataloged any more:
    q = {'portal_type': 'uu.formlibrary.recordfilter'}
    assert len(_search(site, q)) == 0
    # 2. For all measures, things look good:
    q = {'portal_type': MEASURE_DEFINITION_TYPE}
    for brain in _search(site, q):
        measure = _get(brain)
        group = measure.__parent__
        # 2.a. NO _tree; since MeasureDefinition
        # is not subclasing plone.dexterity.content.Container any more
        # in favor of Item, we need to directly access tree:
        assert getattr(aq_base(measure), '_tree', None) is None
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
                    assert is_query_complete(composed.build())
                if measure.denominator_type == 'multi_filter':
                    composed = adapter(u'denominator')
                    assert is_query_complete(composed.build())


def migrate_cachewarm(site):
    cache = DataPointCache(site)
    cache.warm()


def commit(context, msg):
    txn = transaction.get()
    # Undo path, if you want to use it, unfortunately is site-specific,
    # so use the hostname used to access all Plone sites.
    # TODO UNCOMMENT BELOW TODO
    assert txn  # TODO noqa remove this
    #txn.note('%s%s' % (BASEPATH, '/'.join(context.getPhysicalPath())))
    #txn.note(msg)
    #txn.commit()


def migrate(site):
    migrate_measures(site)
    commit(site, 'Migrated measure query filters for %s' % site.getId())
    migrate_cachewarm(site)
    commit(site, 'Warmed data point cache for %s' % site.getId())


def main(app):
    for site in app.objectValues('Plone Site'):
        setSite(site)
        if product_installed(site, PKGNAME):
            migrate(site)


if __name__ == '__main__' and 'app' in locals():
    main(app)  # noqa

