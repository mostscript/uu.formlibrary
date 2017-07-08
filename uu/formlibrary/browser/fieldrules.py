import json

from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFCore.utils import getToolByName
from zope.component.hooks import getSite

from uu.formlibrary.browser.definition import DefinitionCommon


class FieldRulesView(DefinitionCommon):
    """View for managing field rules on a form definition"""

    label = 'Field rules'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()
        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.status = IStatusMessage(request)

    def save_rules(self):
        payload = self.request.get('rules_json', None)
        if payload:
            # validate well-formedness, and re-format with indentation:
            payload = json.dumps(json.loads(payload), indent=2)
            self.context.field_rules = payload
        self.status.addStatusMessage('Saved field rules', type='info')

    def update(self, *args, **kwargs):
        req = self.request
        if req.get('REQUEST_METHOD') == 'POST' and 'saverules' in req:
            self.save_rules()

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)  # provided by template via Five

