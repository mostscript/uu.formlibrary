from Acquisition import aq_parent, aq_inner
from Products.CMFCore.utils import getToolByName

from interfaces import MEASURE_DEFINITION_TYPE, GROUP_TYPE


def local_query(context, query):
    """ 
    Given a catalog search query dict and a context, restrict
    search to items contained in the context path or subfolders.
    
    Returns modified query dict for use with catalog search.
    """
    path = '/'.join(context.getPhysicalPath())
    query['path'] = { 
        'query' : path,
        'depth' : 2,
        }   
    return query


class MeasureLibraryView(object):
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.catalog = getToolByName(context, 'portal_catalog')
        self._brains = {}
        self.definition_type = MEASURE_DEFINITION_TYPE
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
            q = { 'portal_type': portal_type }
            q.update({'sort_on':'modified', 'sort_order': 'descending'})
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


class MeasureDataView(object):
    """
    View that loads cross-product matrix of filters and collections/topics
    inside a measure for purpose of enumerating data values.
    
    This is available for use as an adapter of a measure for purposes of 
    data sources for reports or for use by templates outputting HTML tables
    in a browser view.
    """
    index = None  # overridden by Five magic

    def __init__(self, context, request=None):
        self.context = context
        self.request = request
        self.topics = []
        self.datapoints = {}
    
    def use_percent(self):
        vtype, multiplier = self.context.value_type, self.context.multiplier
        return vtype == 'percentage' and multiplier == 100
    
    def _datasets(self):
        group = aq_parent(aq_inner(self.context))
        return [o for o in group.contentValues() if o.portal_type=='Topic']
    
    def update(self, *args, **kwargs):
        ds = self._datasets()
        self.topics = ds
        for topic in ds:
            topic_id = topic.getId()
            self.datapoints[topic_id] = self.context.dataset_points(topic)
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)
