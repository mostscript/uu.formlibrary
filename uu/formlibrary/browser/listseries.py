from zope.component.hooks import getSite
from Products.CMFCore.utils import getToolByName
from DateTime import DateTime
from zope.schema import getFieldsInOrder

from uu.formlibrary.interfaces import IFormSeries, FORM_TYPES


def local_query(context, query):
    """
    Given a catalog search query dict and a context, restrict
    search to items contained in the context path or subfolders,
    and particularly only items of a form type.

    Returns modified query dict for use with catalog search.
    """
    path = '/'.join(context.getPhysicalPath())
    query['path'] = {
        'query' : path,
        'depth' : 2,
        }
    query['portal_type'] = {
        'query' : FORM_TYPES,
        'operator' : 'or', 
        }
    return query


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
    
    def logourl(self):
        filename = getattr(self.context.logo, 'filename', None)
        if filename is None:
            return None
        base = self.context.absolute_url()
        return '%s/@@download/logo/%s' % (base, filename)
    
    def portalurl(self):
        return getSite().absolute_url()
    
    def groups(self):
        """
        listing groups: returns tuple of dict containing label and result
        sequence of catalog brains from query; template should use these.
        """
        catalog = getToolByName(self.context, 'portal_catalog')
        result = []
        queries = (
            ('Unsubmitted past forms',
                local_query(
                    self.context,
                    {   'review_state' : 'visible',
                        'end' : {
                            'query' : DateTime(), # specify now so...
                            'range' : 'max',      # older than now
                        },
                        'sort_on'       : 'end',
                        'sort_order'    : 'ascending',
                    }
                    )
                ),
            ('Upcoming forms',
                local_query(
                    self.context,
                    {   'review_state' : 'visible',
                        'end' : {
                            'query' : DateTime(), # specify now and...
                            'range' : 'min',      # form end date in future
                        },
                        'sort_on'       : 'start',
                        'sort_order'    : 'ascending',
                    }
                    )
                ),
            ('Submitted recently',
                local_query(
                    self.context,
                    {   'review_state' : 'submitted',
                        'modified' : {
                            'query' : DateTime() - 60, # last 60 days
                            'range' : 'min',
                        },
                        'sort_on'       : 'modified',
                        'sort_order'    : 'descending',
                    }
                    )
                ),
            )
        for label, query in queries:
            result.append({ 'label' : label,
                            'result' : catalog.searchResults(query)})
        return tuple(result)

