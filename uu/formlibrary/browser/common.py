from zope.component.hooks import getSite
from zope.schema import getFieldNamesInOrder

from uu.formlibrary.interfaces import IFormDefinition, IFormSeries


class BaseFormView(object):
  
    VIEWNAME = 'edit'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.portal = getSite()
        self.definition = IFormDefinition(self.context)
        self.series = context.__parent__  # assumes series <>--- form
        self.title = '%s: %s' % (self.series.Title().strip(), context.Title())
        self.seriesinfo = dict(
            [(k, v) for k, v in self.series.__dict__.items()
             if v is not None and k in getFieldNamesInOrder(IFormSeries)]
            )

    def instructions(self):
        _instructions = getattr(self.definition, 'instructions')
        if not _instructions:
            return u''
        return getattr(_instructions, 'output', None) or u''

    def portalurl(self):
        return getSite().absolute_url()

    def logourl(self):
        filename = getattr(self.definition.logo, 'filename', None)
        if filename is None:
            return None
        base = self.definition.absolute_url()
        return '%s/@@download/logo/%s' % (base, filename)

    def browserDefault(self, request):
        # the response does not have access to request; we copy user-agent
        # information to the response for customized handling of exceptions
        # based on user-agent (see uu.formlibrary.patch) with a monkey patch
        # designed to work around Microsoft Office Protocol Discovery,
        # which has MSOffice probe the server first when a hyperlink inside
        # an office document is clicked.
        request.response._req_user_agent = request.get('HTTP_USER_AGENT')
        return self, ()

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

