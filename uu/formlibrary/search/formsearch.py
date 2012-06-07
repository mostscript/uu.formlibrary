from zope.component.hooks import getSite

from uu.formlibrary.interfaces import IMultiForm


class FormSearchView(object):
    """View class for form search page"""

    def __init__(self, context, request):
        if not IMultiForm.providedBy(context):
            raise ValueError('Context must be multi-record form')
        self.context = context
        self.request = request
        self.portal = getSite()

    def portalurl(self):
        return self.portal.absolute_url()

