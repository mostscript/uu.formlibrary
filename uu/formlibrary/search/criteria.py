from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFCore.utils import getToolByName
from zope.component.hooks import getSite
from plone.uuid.interfaces import IUUID

from uu.formlibrary.search.interfaces import IRecordFilter, ICompositeFilter
from uu.formlibrary.search.filters import FilterJSONAdapter

from comparators import Comparators


class BaseFilterView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()

    def used_by(self):
        """
        returns sequence of catalog brains for all content
        (esp. composite filters) referencing/using this filter.
        Uses the getRawRelatedItems index rather than a
        purpose-specific index.
        """
        catalog = getToolByName(self.context, 'portal_catalog')
        uid = IUUID(self.context, None)
        if not uid:
            return ()
        q = {
            'getRawRelatedItems': uid,
            }
        return tuple(catalog.unrestrictedSearchResults(q))

    def portalurl(self):
        return self.portal.absolute_url()


class FilterView(BaseFilterView):
    """
    Summary view for IRecordFilter.
    """

    def __init__(self, context, request):
        if not IRecordFilter.providedBy(context):
            raise ValueError('Context must be a record filter')
        super(FilterView, self).__init__(context, request)
        self.comparators = Comparators(request)

    def queries(self):
        return self.context.values()

    def comparator_title(self, comparator):
        return self.comparators.get(comparator).label

    def comparator_symbol(self, comparator):
        return self.comparators.get(comparator).symbol


class CompositeFilterView(BaseFilterView):
    def __init__(self, context, request):
        super(CompositeFilterView, self).__init__(context, request)

    def setop_title(self, op):
        field = ICompositeFilter['set_operator']
        return [term.title for term in field.vocabulary if term.value == op][0]


class BaseCriteriaView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()
        self.status = IStatusMessage(self.request)

    def update(self, *args, **kwargs):
        req = self.request
        prefix = 'payload-'
        if req.get('REQUEST_METHOD') != 'POST':
            return
        payload_keys = [k for k in self.request.form if k.startswith(prefix)]
        if not payload_keys:
            return
        _info = lambda name: (name.replace(prefix, ''), req.get(name))
        payloads = map(_info, payload_keys)
        for name, payload in payloads:
            rfilter = self.get_filter(name)
            if rfilter is None:
                continue
            adapter = FilterJSONAdapter(rfilter)
            adapter.update(str(payload))
            msg = u'Updated criteria for %s' % rfilter.title
            self.status.addStatusMessage(msg, type='info')
        req.response.redirect(self.context.absolute_url())  # to view tab

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

    def portalurl(self):
        return self.portal.absolute_url()

    def filters(self):
        raise NotImplementedError('base class method')

    def json(self, name):
        """Get JSON payload for record filter, by name"""
        raise NotImplementedError('base class method')

    def get_filter(self, name):
        raise NotImplementedError('base class method')


class FilterCriteriaView(BaseCriteriaView):
    """
    Criteria search form view for a record filter context.
    """

    def get_filter(self, name):
        return self.context

    def filters(self):
        return [self.context]

    def json(self, name):
        """Get JSON payload for record filter, by name"""
        return FilterJSONAdapter(self.context).serialize()


class MeasureCriteriaView(BaseCriteriaView):

    def get_filter(self, name):
        if name not in self.context.objectIds():
            return None
        return self.context.get(name)

    def filters(self):
        _isrfilter = lambda o: o.portal_type == 'uu.formlibrary.recordfilter'
        return filter(_isrfilter, self.context.contentValues())

    def json(self, name):
        """Get JSON payload for record filter, by name"""
        if name not in self.context.objectIds():
            return '{}'
        rfilter = self.context.get(name)
        return FilterJSONAdapter(rfilter).serialize()

