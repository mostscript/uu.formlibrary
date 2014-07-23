from Acquisition import aq_parent, aq_inner
from OFS.event import ObjectClonedEvent
from plone.app.content.namechooser import NormalizingNameChooser
from plone.app.uuid.utils import uuidToCatalogBrain
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import getMultiAdapter
from zope.event import notify
from zope.lifecycleevent import ObjectCopiedEvent
from zope.schema import getFieldNamesInOrder

from uu.formlibrary.interfaces import IFormDefinition
from interfaces import IMeasureDefinition
from interfaces import MEASURE_DEFINITION_TYPE, GROUP_TYPE, DATASET_TYPE
from interfaces import AGGREGATE_LABELS


def local_query(context, query):
    """
    Given a catalog search query dict and a context, restrict
    search to items contained in the context path or subfolders.

    Returns modified query dict for use with catalog search.
    """
    path = '/'.join(context.getPhysicalPath())
    query['path'] = {
        'query': path,
        'depth': 2,
        }
    return query


class MeasureLibraryView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.catalog = getToolByName(context, 'portal_catalog')
        self._brains = {}
        self.definition_type = MEASURE_DEFINITION_TYPE
        self.dataset_type = DATASET_TYPE
        self.group_type = GROUP_TYPE
        self.topic_type = 'Topic'

    def recent(self, limit=None, portal_type=None):
        """
        Return catalog brains (metadata) of most recent
        measure definitions contained within this library.

        To limit results, pass in an integer value to limit.
        """
        if portal_type is None:
            portal_type = self.definition_type
        if portal_type not in self._brains:
            q = {'portal_type': portal_type}
            q.update({'sort_on': 'modified', 'sort_order': 'descending'})
            q = local_query(self.context, q)
            r = self.catalog.searchResults(q)
            self._brains[portal_type] = r
        if limit is not None:
            return self._brains[portal_type][:limit]
        return self._brains[portal_type]

    def count(self, portal_type=None):
        return len(self.recent(portal_type=portal_type))

    def searchpath(self):
        return '/'.join(self.context.getPhysicalPath())


class FormDataSetView(object):
    """Default view for IFormDataSetSpecification"""

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.forms = []

    def aggregate_label(self):
        fn = getattr(self.context, 'aggregate_function', 'AVG')
        return dict(AGGREGATE_LABELS).get(fn)  # get function label

    def dataset_info(self, uid):
        return uuidToCatalogBrain(uid)

    def update(self):
        req = self.request
        if req.get('REQUEST_METHOD', 'GET') == 'POST' and 'clone' in req:
            print 'TODO: cloning'
        self.forms = self.context.forms()

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)  # via framework magic


class FormDataSetCloningView(object):
    """View for cloning a dataset, acting as a factory for a copy"""

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.forms = []
        self.status = IStatusMessage(self.request)

    def target_id(self, target, parent):
        """Given a target and parent, generate new id"""
        generated_id = NormalizingNameChooser(parent).chooseName(
            None,
            target,
            )  # name from title, incidentally avoids colliding w/ source id
        return generated_id

    def update(self):
        req = self.request
        if req.get('REQUEST_METHOD', 'GET') == 'POST' and 'makeclone' in req:
            source = self.context
            parent = source.__parent__
            target = source._getCopy(parent)
            target.title = req.get('clone_title', source.title).decode('utf-8')
            target.description = req.get(
                'clone_description',
                source.description,
                ).decode('utf-8')
            target_id = self.target_id(target, parent)
            target._setId(target_id)
            notify(ObjectCopiedEvent(target, source))
            parent._setObject(target_id, target)
            target = parent.get(target_id)
            target.wl_clearLocks()
            notify(ObjectClonedEvent(target))
            self.status.add(
                u'Created a new data set with title "%s" cloned from '
                u'original data set "%s"' % (target.title, source.title),
                type=u'info',
                )
            req.response.redirect(target.absolute_url() + '/edit')

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)  # via framework magic


class MeasureBaseView(object):
    """Shared view capabilities for data view and core view of measure"""

    index = None  # overridden by Five magic

    def __init__(self, context, request=None):
        self.context = context
        self.request = request
        self.datasets = []
        self.datapoints = {}
        self.schema = IFormDefinition(self.context).schema
        self.fieldnames = getFieldNamesInOrder(self.schema)

    def use_percent(self):
        vtype, multiplier = self.context.value_type, self.context.multiplier
        return vtype == 'percentage' and multiplier == 100

    def choice_label(self, fieldname):
        field = IMeasureDefinition[fieldname]
        vocab = field.vocabulary
        v = getattr(self.context, fieldname, field.default)
        if v is None:
            return ''
        if callable(vocab):
            vocab = vocab(self.context)
        return vocab.getTerm(v).title

    def _datasets(self):
        group = aq_parent(aq_inner(self.context))
        ftiname = DATASET_TYPE
        return [o for o in group.contentValues() if o.portal_type == ftiname]

    def source_type(self):
        return aq_parent(aq_inner(self.context)).source_type

    def criteria_view(self):
        return getMultiAdapter(
            (self.context, self.request),
            name='measure_criteria',
            )

    def update(self, *args, **kwargs):
        self.datasets = self._datasets()

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

    def filtervalues(self, rfilter):
        raw = rfilter.values()
        return [query for query in raw if query.fieldname in self.fieldnames]


class MeasureDataView(MeasureBaseView):
    """
    View that loads cross-product matrix of filters and collections/topics
    inside a measure for purpose of enumerating data values.

    This is available for use as an adapter of a measure for purposes of
    data sources for reports or for use by templates outputting HTML tables
    in a browser view.
    """

    def update(self, *args, **kwargs):
        self.datasets = self._datasets()
        for dataset in self.datasets:
            dsid = dataset.getId()
            self.datapoints[dsid] = self.context.dataset_points(dataset)

