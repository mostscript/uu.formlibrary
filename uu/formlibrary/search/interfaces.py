from zope.interface import Interface
from zope.interface.common.mapping import IIterableMapping
from zope.publisher.interfaces import IPublishTraverse
from zope import schema


API_VERSION = 1


class ISearchAPICapability(IPublishTraverse):
    """
    Interface for an API capability that is an object-published
    component.
    """
    
    def __call__(*args, **kwargs):
        """
        return simple Python data structure such as dict,
        list, or if necessary a specific component for the
        capability.
        """
    
    def index_html(self, REQUEST=None):
        """
        Return JSON representation of data returned from call.
        Used over-the-web for HTTP APIs.
        """


class IComparator(Interface):
    """An individual comparator's metadata."""
    
    name = schema.TextLine(
        title=u'Comparator name',
        description=u'Identifier for comparator.',
        required=True,
        )
    
    label = schema.TextLine(
        title=u'Label',
        description=u'Label or title for comparator; displayed in forms; '\
                    u'this is typically a verb/predicate phrase.',
        required=False,
        )
    
    description = schema.Text(
        title=u'Description',
        description=u'Description or help text for comparator.',
        required=False,
        )
    
    symbol = schema.TextLine(
        title=u'Unicode symbol',
        description=u'One or a few characters of Unicode text '\
                    u'representing an operator symbol or glyph.',
        required=False,
        )



class IComparators(ISearchAPICapability, IIterableMapping):
    """Mapping interface listing comparator metadata."""
    
    def keys():
        """Names of comparators as unicode objects."""
    
    def __getitem__(name):
        """Get a comparator by name providing IComparator"""



class IFilters(ISearchAPICapability, IIterableMapping):
    """
    Mapping interface for obtaining field names, comparators and
    metadata for a field, and widget and/or vocabularies.
    """


class ISearchAPI(IIterableMapping, IPublishTraverse):
    """
    Search API interface: common API for over-the-web (JSON) use and 
    use in Python.  This interface is an entry point for specific
    search-related capabililties for querying uu.formlibrary form data
    and constructing search forms (dynamically, usually via JavaScript)
    for query construction.
    
    Has mapping interface listing names of capabilities, along with 
    capability object values.
    """
    
    version = schema.Int(
        readonly=True,
        default=API_VERSION,
        )
    
    comparators = schema.Object(
        title=u'Comparators',
        description=u'Comparators metadata capability; this is, '\
                    u'in theory, independent of the context.',
        schema=IComparators,
        )
    
    filters = schema.Object(
        title=u'Filters',
        description=u'Filters information metadata capability, '\
                    u'dependent on context for schema information; '\
                    u'the enumeration of filters is a one-to-one '\
                    u'mapping to the enumeration of schema fields.',
        schema=IFilters,
        )
    
    def __call__(*args, **kwargs):
        """
        Return text string 'Form search API' plus version, along
        with a human-readable listing of capability names 
        ('comparators', 'filters', etc).
        """

