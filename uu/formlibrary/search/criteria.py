from zope.component.hooks import getSite

from uu.formlibrary.search.interfaces import IRecordFilter


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

    def portalurl(self):
        return self.portal.absolute_url()

