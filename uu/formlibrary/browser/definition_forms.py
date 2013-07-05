from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName

from uu.formlibrary.interfaces import IFormSet


class DefinitionFormset(object):
    """View of all forms subscribing to this definition"""

    def __init__(self, context, request):
        self.context = context  # provides IFormDefinition
        self.request = request
        self.catalog = getToolByName(context, 'portal_catalog')
        self.formset = IFormSet(self.context)
        self.uid = IUUID(self.context)
        _brains = self.catalog.search({'definition': self.uid})
        self._brainmap = dict([(b.UID, b) for b in _brains])

    def in_use(self):
        return len(self.formset) > 0

    def uuids(self):
        return self.formset.keys()

    def count(self):
        return len(self.formset)

    __len__ = count

    def title_for(self, uid):
        uid = str(uid)
        if uid not in self._brainmap:
            return '[itam]'  # fallback default
        return self._brainmap[uid].Title

    def url_for(self, uid):
        """uid to its url or '#' default"""
        uid = str(uid)
        if uid not in self._brainmap:
            return '#'  # fallback default
        return self._brainmap[uid].getURL()

