from Products.CMFCore.utils import getToolByName

from uu.formlibrary.interfaces import DEFINITION_TYPE


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


class LibraryView(object):
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.catalog = getToolByName(context, 'portal_catalog')
        self._brains = None
        self.definition_type = DEFINITION_TYPE
    
    def recent(self, limit=None):
        """
        Return catalog brains (metadata) of most recent 
        form definitions contained within this library.
        
        To limit results, pass in an integer value to limit.
        """
        if self._brains is None:
            q = {'portal_type': self.definition_type}
            q.update({'sort_on':'modified', 'sort_order': 'decscending'})
            q = local_query(self.context, q)
            r = self.catalog.searchResults(q)
            self._brains = r
        if limit is not None:
            return self._brains[:limit]
        return self._brains
    
    def count(self):
        return len(self.recent())
    
    def searchpath(self):
        return '/'.join(self.context.getPhysicalPath())

