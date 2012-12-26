import math

from Acquisition import aq_parent, aq_inner
from plone.dexterity.content import Container
from zope.component.hooks import getSite
from zope.interface import implements

from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.search.filters import filter_query
from interfaces import IMeasureDefinition, IMeasureGroup, IMeasureLibrary
from utils import content_path


# measure definition content type class:

class MeasureDefinition(Container):
    """Metadata about a measure"""
    
    implements(IMeasureDefinition)
     
    portal_type = 'uu.formlibrary.measure'
    
    def _source_type(self):
        group = aq_parent(aq_inner(self))
        return group.source_type
    
    def _mr_raw_numerator(self, context):
        """Get raw value for numerator n"""
        if self.numerator_type == 'constant':
            n = 1
        if self.numerator_type == 'multi_total':
            n = len(context)
        if self.numerator_type == 'multi_filter':
            rfilter = self['numerator']     # get contained filter
            q = filter_query(rfilter)       # repoze.catalog query object
            n = context.catalog.rcount(q)   # result count from form's embedded catalog
        return n
    
    def _mr_raw_denominator(self, context):
        """Get raw value for denominator m"""
        # denominator m:
        if self.denominator_type == 'constant':
            m = 1
        if self.denominator_type == 'multi_total':
            m = len(context)
        if self.denominator_type == 'multi_filter':
            rfilter = self['denominator']   # get contained filter
            q = filter_query(rfilter)       # repoze.catalog query object
            m = context.catalog.rcount(q)   # result count from form's embedded catalog
        return m
    
    def _mr_values(self, context):
        """return (n, m) values for numerator, denominator"""
        n = self._mr_raw_numerator(context)
        m = self._mr_raw_denominator(context)
        return (n, m)

    def _flex_value(self, context):
        raise NotImplementedError('todo')   # TODO
    
    def raw_value(self, context):
        """
        Get raw value (no rounding or constant multiple), given a form
        instance.
        """
        source_type = self._source_type()
        if source_type == MULTI_FORM_TYPE:
            nan = float('NaN')
            divide = lambda a,b: float(a) / float(b) if b else nan
            return divide(*self._mr_value(context))
        return self._flex_form_value(context)
    
    def _normalize(self, v):
        if math.isnan(v):
            return v
        ## constant multiplier
        v = self.multiplier * v  # multiplier defaults to 1.0
        ## rounding
        rrule = self.rounding
        if rrule:
            fn = {
                'round' : round,
                'ceiling' : math.ceil,
                'floor' : math.floor,
                }.get(rrule, round)
            v = fn(v)
        if self.value_type == 'count':
            return int(v)  # count is always whole numbers
        return v  # floating point value, normalized
    
    def _values(self, context):
        """Return raw and normalized value as a two item tuple"""
        raw = self.raw_value(context)
        return (raw, self._normalize(raw))
    
    def value_for(self, context):
        """ 
        Given an appropriate form context, compute a value, normalize
        as appropriate.
        """
        return self._values()[1]
    
    def datapoint(self, context):
        """Returns dict for data point given form context"""
        n = m = None
        if self._source_type() == MULTI_FORM_TYPE and self.denominator_type != 'constant':
            n, m = self._mr_values(context)
            nan = float('NaN')
            divide = lambda a,b: float(a) / float(b) if b else nan
            raw = divide(n, m)
            normalized = self._normalize(raw)
        else:
            raw, normalized = self._values(context)
        point_record = { 
            'title': context.Title(),
            'url': context.absolute_url(),
            'path' : content_path(context),
            'start': context.start,
            'value': normalized,
            'raw_value' : raw,
            'display_value' : self.display_format(normalized),
        }
        if n is not None:
            point_record['raw_numerator'] = n
        if m is not None:
            point_record['raw_denominator'] = m
        return point_record
    
    def points(self, seq):
        """
        Given iterable seq of form instance contexts, return a list
        of datapoints for each.
        """
        return [self.datapoint(context) for context in seq]

    def _dataset_search(self, q):
        catalog_tool = getSite().portal_catalog
        return catalog_tool.search(q)

    def dataset_points(self, dataset):
        """Given a topic/collection object dataset, return point values"""
        topic_q = dataset.buildQuery()
        forms = [
            b._unrestrictedGetObject() for b in self._dataset_search(topic_q)
            ]
        return self.points(forms)
    
    def display_format(self, value):
        """ 
        Format a value as a string using rules defined on measure
        definition.
        """
        if math.isnan(value):
            return 'N/A'
        fmt = '%%.%if' % self.display_precision
        if self.value_type == 'percentage' and self.multiplier == 100.0:
            fmt += '%%'
        return fmt % value
    
    def display_value(self, context):
        """ 
        Return string display value (formatted) for context.
        """
        return self.display_format(self.value_for(context))


# measure group content type class:

class MeasureGroup(Container):
    """
    Container/folder for measures and shared topics, bound
    to a form definition and source type common to all contained
    measures.
    """
    
    implements(IMeasureGroup)
   
    portal_type = 'uu.formlibrary.measuregroup'


# measure library content type class:

class MeasureLibrary(Container):
    """Library contains measure groups and measures within them"""
    
    implements(IMeasureLibrary)
   
    portal_type = 'uu.formlibrary.measurelibrary'

