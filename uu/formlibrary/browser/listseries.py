from zope.component.hooks import getSite
from Products.CMFCore.utils import getToolByName
from DateTime import DateTime
from zope.schema import getFieldsInOrder

from uu.formlibrary.interfaces import IFormSeries, FORM_TYPES
from uu.formlibrary.utils import local_query


class FormSeriesListing(object):
    """ default view for series listing """

    VIEWNAME = 'view'   # here to satisfy common macros
    SERIES = True       # avoids call from template to portal_interface tool

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.user_message = ''
        self.seriesinfo = {}
        for name, field in getFieldsInOrder(IFormSeries):
            self.seriesinfo[name] = getattr(context, name, field.default)
        self.title = context.Title()
        self.catalog = getToolByName(self.context, 'portal_catalog')
        self.workflow = getToolByName(self.context, 'portal_workflow')

    def logourl(self):
        filename = getattr(self.context.logo, 'filename', None)
        if filename is None:
            return None
        base = self.context.absolute_url()
        return '%s/@@download/logo/%s' % (base, filename)

    def portalurl(self):
        return getSite().absolute_url()

    def is_recently_submitted(self, brain):
        form = self.context.get(brain.getId)
        wfid = self.workflow.getChainFor(form)[0]
        submit_actions = filter(
            lambda action: action.get('action') == 'submit',
            self.workflow.getHistoryOf(wfid, form)
            )
        last = None if not submit_actions else submit_actions[-1]
        return last.get('time') > (DateTime() - 60)

    def search(self, label, query):
        result = self.catalog.searchResults(query)
        if label == 'Submitted recently':
            result = filter(self.is_recently_submitted, result)
        return result

    def groups(self):
        """
        listing groups: returns tuple of dict containing label and result
        sequence of catalog brains from query; template should use these.
        """
        result = []
        queries = (
            (
                'Unsubmitted past forms',
                local_query(
                    self.context,
                    {
                        'review_state': 'visible',
                        'end': {
                            'query': DateTime(),  # specify now so...
                            'range': 'max',       # older than now
                        },
                        'sort_on': 'end',
                        'sort_order': 'ascending',
                    },
                    types=FORM_TYPES,
                    )
                ),
            (
                'Upcoming forms',
                local_query(
                    self.context,
                    {
                        'review_state': 'visible',
                        'end': {
                            'query': DateTime(),  # specify now and...
                            'range': 'min',       # form end date in future
                        },
                        'sort_on': 'start',
                        'sort_order': 'ascending',
                    },
                    types=FORM_TYPES,
                    )
                ),
            (
                'Submitted recently',
                local_query(
                    self.context,
                    {
                        'review_state': {
                            'query': ('submitted', 'archived'),
                            'operator': 'or',
                        },
                        'modified': {
                            'query': DateTime() - 60,  # last 60 days
                            'range': 'min',
                        },
                        'sort_on': 'modified',
                        'sort_order': 'descending',
                    },
                    types=FORM_TYPES,
                    )
                ),
        )
        for label, query in queries:
            result.append({'label': label,
                           'result': self.search(label, query)})
        return tuple(result)

