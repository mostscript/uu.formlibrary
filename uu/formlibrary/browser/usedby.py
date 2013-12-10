from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName


class InUseBy(object):
    """View of objects referencing the context"""

    INDEX = 'references'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.catalog = getToolByName(context, 'portal_catalog')
        self.uid = IUUID(self.context)
        _brains = self.catalog.unrestrictedSearchResults(
            {self.INDEX: self.uid}
            )
        self._brainmap = dict([(b.UID, b) for b in _brains])

    def uuids(self):
        return self._brainmap.keys()

    def count(self):
        return len(self._brainmap)

    def in_use(self):
        return self.count() > 0

    __len__ = count

    def title_for(self, uid):
        uid = str(uid)
        if uid not in self._brainmap:
            return '[item]'  # fallback default
        return self._brainmap[uid].Title

    def url_for(self, uid):
        """uid to its url or '#' default"""
        uid = str(uid)
        if uid not in self._brainmap:
            return '#'  # fallback default
        return self._brainmap[uid].getURL()

