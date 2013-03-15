import datetime
import math

from Acquisition import aq_parent, aq_inner, aq_base
from DateTime import DateTime
from plone.dexterity.content import Container, Item
from plone.uuid.interfaces import IUUID
from zope.component.hooks import getSite
from zope.interface import implements

from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.search.filters import filter_query
from uu.formlibrary.search.interfaces import IRecordFilter

from interfaces import IMeasureDefinition, IMeasureGroup, IMeasureLibrary
from interfaces import IFormDataSetSpecification
from utils import content_path


# measure definition content type class:

class MeasureDefinition(Container):
    """Metadata about a measure"""
    
    implements(IMeasureDefinition)
     
    portal_type = 'uu.formlibrary.measure'
    
    def group(self):
        return aq_parent(aq_inner(self))  # folder containing
    
    def _source_type(self):
        return self.group().source_type

    def _mr_get_value(self, context, name):
        """Get raw value for numerator or denominator"""
        assert name in ('numerator', 'denominator')
        vtype = getattr(self, '%s_type' % name, None)
        v = 1 if vtype == 'constant' else None  # initial value
        if vtype == 'multi_total':
            v = len(context)
        if vtype == 'multi_filter':
            rfilter = self.get(name)            # get contained filter
            if rfilter is None or not IRecordFilter.providedBy(rfilter):
                return v
            # get embedded catalog for the form:
            catalog = getattr(aq_base(context), 'catalog', None)
            if catalog is None:
                return v
            q = filter_query(rfilter)           # repoze.catalog query object
            v = catalog.rcount(q)               # result count from catalog
        return v
 
    def _mr_values(self, context):
        """return (n, m) values for numerator, denominator"""
        n = self._mr_get_value(context, name='numerator')
        m = self._mr_get_value(context, name='denominator')
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
            return divide(*self._mr_values(context))
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

    def dataset_points(self, dataset):
        """
        Given an data set specification object providing the interface
        IFormDataSetSpecification, return data points for all forms
        included in the set.
        """
        forms = dataset.forms()
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
    
    def value_note(self, info):
        """
        Given a datapoint dict, create a textual note as addendum
        for display adjacent to value.
        """
        note = u''
        if 'raw_numerator' in info and 'raw_denominator' in info:
            note += u'%s of %s' % (
                info.get('raw_numerator'),
                info.get('raw_denominator'),
                )
            if self.denominator_type == 'multi_filter':
                note += u' (filtered)'
            note += u' records'
        return note or None  # return None instead of empty note


# measure group content type class:

class MeasureGroup(Container):
    """
    Container/folder for measures and shared datasets, bound
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


## data set:

class FormDataSetSpecification(Item):
    implements(IFormDataSetSpecification)
    
    def included_locations(self):
        """
        Returns catalog brains for each location in locations field.
        """
        catalog = getSite().portal_catalog
        spec_uids = getattr(self, 'locations', []) 
        if not spec_uids:
            return None
        q = { 'UID' : {'query': spec_uids, 'operator': 'or', 'depth':0} }
        return catalog.search(q)
    
    def directly_included(self, spec):
        """
        Given spec as either UID, form object, or brain, return True if
        the form object is directly included in the locations field, or
        return False if merely indirectly included.
        """
        if not isinstance(spec, basestring):
            if hasattr(spec, 'getRID') and hasattr('UID'):
                spec = spec.UID  # catalog brain with UID attr
            else:
                spec = IUUID(spec, None)
                if spec is None:
                    return False
        spec = str(spec)
        return spec in self.locations
    
    def _path_query(self):
        spec_uids = getattr(self, 'locations', []) 
        if not spec_uids:
            return None
        # first use catalog to get brains for all matches to these
        # UIDs where portal_type is MULTI_FORM_TYPE
        catalog = getSite().portal_catalog
        filter_q = { 
            'portal_type': MULTI_FORM_TYPE,
            'UID': {
                'query': spec_uids,
                'operator': 'or',
                },  
            }   
        form_uids = [b.UID for b in catalog.search(filter_q)]
        folder_uids = list(set(spec_uids).difference(form_uids))
        folder_q = { 'UID' : {'query': folder_uids, 'operator': 'or'} }
        folder_paths = [b.getPath() for b in catalog.search(folder_q)]
        path_q = { 
            'portal_type': MULTI_FORM_TYPE,
            'path': {
                'query': folder_paths,
                'operator': 'or',
                },
            }
        return path_q, form_uids

    def _query_spec(self):
        idxmap = { 
            'query_title' : 'Title',
            'query_subject' : 'Subject',
            'query_state' : 'review_state',
        }
        q = {}
        pathq, form_uids = self._path_query()
        if pathq is not None:
            q.update(pathq)  # include folder specified
        for name in idxmap:
            idx = idxmap[name]
            v = getattr(self, name, None)
            if isinstance(v, datetime.date):
                v = datetime.datetime(*v.timetuple()[:7]) # internal convert
            if isinstance(v, datetime.datetime):
                v = DateTime(v)
            if v:
                # only non-empty values are considered
                q[idx] = v
        _DT = lambda d: DateTime(datetime.datetime(*d.timetuple()[:7]))
        if self.query_start and self.query_end:
            q['start'] = {
                'query': (_DT(self.query_start), _DT(self.query_end)),
                'range' : 'min:max',
                }
        if self.query_start and not self.query_end:
            q['start'] = {
                'query': _DT(self.query_start),
                'range' : 'min',
                }
        if self.query_end and not self.query_start:
            q['start'] = {
                'query': _DT(self.query_end),
                'range' : 'max',
                }
        return q, form_uids
    
    def brains(self):
        folder_query, form_uids = self._query_spec()
        catalog = getSite().portal_catalog
        directly_specified = catalog.search({
            'UID' : {'query': form_uids, 'operator': 'or'},
            })  
        forms_in_folders_specified = catalog.search(folder_query)
        # get a LazyCat (concatenation of two results):
        unsorted_result = directly_specified + forms_in_folders_specified
        # might as well get all the results into list instead of LazyCat:
        unsorted_result = list(unsorted_result)
        if not getattr(self, 'sort_on_start', False):
            return unsorted_result
        _keyfn = lambda brain: getattr(brain, 'start', None)
        return sorted(unsorted_result, key=_keyfn)

    def forms(self):
        r = self.brains()
        _get = lambda brain: brain._unrestrictedGetObject()
        return [_get(b) for b in r]

