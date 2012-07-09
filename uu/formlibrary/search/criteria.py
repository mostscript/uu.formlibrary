from Products.statusmessages.interfaces import IStatusMessage
from zope.component.hooks import getSite

from uu.formlibrary.search.interfaces import IRecordFilter
from uu.formlibrary.search.filters import FilterJSONAdapter

from comparators import Comparators


class FilterView(object):
    """
    Summary view for IRecordFilter.
    """
    
    def __init__(self, context, request):
        if not IRecordFilter.providedBy(context):
            raise ValueError('Context must be a record filter')
        self.context = context
        self.request = request
        self.comparators = Comparators(request)
    
    def queries(self):
        return self.context.values()
    
    def comparator_title(self, comparator):
        return self.comparators.get(comparator).label


class FilterCriteriaView(object):
    """
    Criteria search form view for a record filter context.
    """

    def __init__(self, context, request):
        if not IRecordFilter.providedBy(context):
            raise ValueError('Context must be a record filter')
        self.context = context
        self.request = request
        self.portal = getSite()
        self.status = IStatusMessage(self.request)
    
    def update(self, *args, **kwargs):
        payload = self.request.form.get('payload', None)
        if payload is not None:
            adapter = FilterJSONAdapter(self.context)
            adapter.update(str(payload))
            msg = u'Updated criteria'
            self.status.addStatusMessage(msg, type='info')
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)
    
    def portalurl(self):
        return self.portal.absolute_url()

