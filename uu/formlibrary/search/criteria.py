from plone.uuid.interfaces import IUUID
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import queryAdapter
from zope.component.hooks import getSite
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent

from uu.workflows.utils import history_log
from uu.formlibrary.search.interfaces import IComposedQuery
from uu.formlibrary.search.filters import FilterJSONAdapter

from comparators import Comparators


class MeasureCriteriaView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()
        self.comparators = Comparators(request)
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
        log_messages = []
        for name, payload in payloads:
            rfilter = self.get_filter(name)
            if rfilter is None:
                continue
            adapter = FilterJSONAdapter(rfilter)
            adapter.update(str(payload))
            queryname = rfilter.__parent__.__parent__.name
            msg = u'Updated criteria for %s' % queryname
            self.status.addStatusMessage(msg, type='info')
            log_messages.append(msg)
        history_log(
            self.context,
            message='\n'.join(log_messages),
            set_modified=True,
            )
        notify(ObjectModifiedEvent(self.context))
        req.response.redirect(self.context.absolute_url())  # to view tab

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

    def portalurl(self):
        return self.portal.absolute_url()

    def include_queries(self):
        include = []
        if self.context.numerator_type == 'multi_filter':
            include.append('numerator')
        if self.context.denominator_type == 'multi_filter':
            include.append('denominator')
        return include

    def composed_query(self, name):
        return queryAdapter(self.context, IComposedQuery, name=name)

    def composed_queries(self):
        return [self.composed_query(name) for name in self.include_queries()]

    def get_filter(self, name):
        match = [info for info in self.filters() if info.get('uid') == name]
        if not match:
            return None
        return match[0].get('filter')

    def find_filters(self, composed):
        r = []
        for group in composed:
            for rfilter in group:
                r.append(rfilter)
        return r

    def filters(self):
        if not hasattr(self, '_filters'):
            self._filters = []
            included = self.include_queries()
            for name in included:
                title = name.title()
                composed = self.composed_query(name)
                found = self.find_filters(composed)
                if found:
                    rfilter = found[0]
                    self._filters.append({
                        'uid': IUUID(rfilter),
                        'title': title,
                        'filter': rfilter,
                        })
        return self._filters

    def json(self, name):
        """Get JSON payload for record filter, by name (uid)"""
        match = [info for info in self.filters() if info.get('uid') == name]
        if not match:
            return '{}'   # no matching filter
        rfilter = match[0].get('filter')
        return FilterJSONAdapter(rfilter).serialize()

    def comparator_title(self, comparator):
        return self.comparators.get(comparator).label

    def comparator_symbol(self, comparator):
        return self.comparators.get(comparator).symbol

