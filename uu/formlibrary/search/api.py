import itertools

from zope.interface import implements
from zope.publisher.interfaces import IPublishTraverse, NotFound

from uu.formlibrary.search.interfaces import ISearchAPI, API_VERSION
from comparators import Comparators


class SearchAPI(object):
    """
    Browser view entry point for API capabilities.
    """
    
    CAPABILITIES = ['comparators',] # 'filters']
    
    implements(IPublishTraverse, ISearchAPI)

    def __init__(self, context, request=None):
        self.context = context
        self.request = None
        self.version = API_VERSION
        self.comparators = Comparators(request)
        self.filters = None  # TODO: implement
        self._capabilities_security_context()
    
    def _capabilities_security_context(self):
        """
        Set __parent__ pointers on all API capability components,
        which means that they will appear to Zope2 AccessControl
        as being in the aquisition context of the application
        containing the accessing user.  Which works because the 
        machinery thinks this view object is in that aquisition
        context, whether via __parent__ or aquisition parents.  
        
        Implication: this allows the creation of capability component
        classes that do not need to subclass Acquisition.Implicit. This
        simplifies the writing of API capabilities.
        """
        for name in self.CAPABILITIES:
            c = self.get(name)
            if c is not None:
                c.__parent__ = self
    
    def __call__(self, *args, **kwargs):
        banner = 'Form search API, version %s' % self.version
        msg = '\n'.join([banner, '\n== Capabilities ==\n'] + self.CAPABILITIES)
        if self.request is not None:
            self.request.response.setHeader('Content-type', 'text/plain')
            self.request.response.setHeader('Content-length', str(len(msg)))
        return msg
    
    def get(self, name, default=None):
        name = str(name)
        if name not in self.CAPABILITIES:
            return default
        return getattr(self, name, None)
    
    def __getitem__(self, name):
        v = self.get(name)
        if v is None:
            raise KeyError(name)
        return v
    
    def keys(self):
        return self.CAPABILITIES
    
    def iterkeys(self):
        return self.keys().__iter__()
    
    def itervalues(self):
        return itertools.imap(lambda k: self.get(k), self.keys())
    
    def iteritems(self):
        return itertools.imap(lambda k: (k, self.get(k)), self.keys())
    
    def values(self):
        return list(self.itervalues())
    
    def items(self):
        return list(self.iteritems())
    
    def __contains__(self, name):
        return str(name) in self.capabilities
    
    def __len__(self):
        return len(self.capabilities)
    
    def publishTraverse(self, request, name):
        if name in self.CAPABILITIES:
            return self.get(name)
        raise NotFound(self, name, request)

