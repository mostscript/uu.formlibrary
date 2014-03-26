from Acquisition import aq_parent, aq_inner
from plone.uuid.interfaces import IUUID
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import queryAdapter
from zope.component.hooks import getSite
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent

from uu.workflows.utils import history_log
from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.interfaces import MULTI_FORM_TYPE
from uu.formlibrary.search.interfaces import IComposedQuery
from uu.formlibrary.search.filters import FilterJSONAdapter

from comparators import Comparators


class MeasureCriteriaActions(object):
    """
    Helper methods for object tab action conditions; show_criteria()
    and show_advanced() should be mututally exclusive.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.adv = 'advanced' in self.request.get('PATH_INFO').split('/')[-1]

    def show_criteria(self):
        if self.adv:
            return False
        group = aq_parent(aq_inner(self.context))
        return group.source_type == MULTI_FORM_TYPE

    def show_advanced(self):
        return self.adv

    def __call__(self, *args, **kwargs):
        return 'Actions helper'


class MeasureCriteriaView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()
        self.comparators = Comparators(request)
        self.status = IStatusMessage(self.request)
        self.schema = IFormDefinition(self.context).schema
        print self.request.get('PATH_INFO')  # TODO remove
        self.advanced, self.redirect = self.requires_advanced()

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
            adapter = FilterJSONAdapter(rfilter, self.schema)
            adapter.update(str(payload))
            queryname = self.filter_groupname(rfilter)
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

    def _query(self, name):
        return queryAdapter(
            self.context,
            IComposedQuery,
            name=name,
            )

    def requires_advanced(self, names=(u'numerator', u'denominator')):
        """
        Returns a two-boolean tuple, the first for whether the query
        requires advanced, the second if the view requires a redirect
        to the advanced editor.

        If either numerator or denominator needs adavanced (nested)
        editor, the first element should return True.  Likewise, if
        the view dictates use of advanced.

        The second element should only return True (redirect needed) if
        the query requires advanced editing, but the view is basic.
        """
        adv = 'advanced' in self.request.get('PATH_INFO').split('/')[-1]
        _useadv = lambda q: q.requires_advanced_editing()
        adv_query = any(map(_useadv, map(self._query, names)))
        return (adv or adv_query, adv_query and not adv)

    def __call__(self, *args, **kwargs):
        if self.redirect:
            url = '%s/%s' % (
                self.context.absolute_url(),
                '@@advanced_criteria',
                )
            self.request.response.redirect(url)
            return
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

    def filter_groupname(self, rfilter):
        uid = IUUID(rfilter)
        r = [d.get('groupname') for d in self._filters if d.get('uid') == uid]
        return r[0]

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
                        'groupname': name,
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
        return FilterJSONAdapter(rfilter, self.schema).serialize()

    def comparator_title(self, comparator):
        return self.comparators.get(comparator).label

    def comparator_symbol(self, comparator):
        return self.comparators.get(comparator).symbol

