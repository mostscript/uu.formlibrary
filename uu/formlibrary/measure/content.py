import datetime
from itertools import chain
import math

from Acquisition import aq_parent, aq_inner, aq_base
from DateTime import DateTime
from plone.dexterity.content import Container, Item
from plone.indexer.decorator import indexer
from plone.memoize import ram
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from plone.app.layout.navigation.root import getNavigationRoot
from pytz import UTC
from repoze.catalog import query
from zope.component import queryAdapter
from zope.component.hooks import getSite
from zope.interface import implements

from uu.formlibrary.interfaces import MULTI_FORM_TYPE
from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.search.interfaces import IComposedQuery
from uu.formlibrary.search.filters import composed_storage

from interfaces import IMeasureDefinition, IMeasureGroup, IMeasureLibrary
from interfaces import IFormDataSetSpecification
from interfaces import AGGREGATE_FUNCTIONS, AGGREGATE_LABELS
from utils import content_path, isbrain, get
from cache import datapoint_cache_key, DataPointCache


# sentinel value:
NOVALUE = float('NaN')


DT = lambda d: DateTime(datetime.datetime(*d.timetuple()[:7], tzinfo=UTC))


@indexer(IMeasureDefinition)
def measure_subjects_indexer(context):
    base = list(context.Subject())
    if getattr(context, 'goal', None) is not None:
        base += ['goal_value_%s' % context.goal]
    return tuple(base)


@indexer(IMeasureGroup)
def group_references(context):
    return [context.definition]


def is_query_complete(q):
    """
    Checks for incomplete queries; if any part of the query
    contains repoze.catalog.query.BoolOp queries that are not
    completed, this should return False.
    """
    if isinstance(q, query.BoolOp):
        if not q.queries:
            return False
        return all(map(is_query_complete, q.queries))
    return True   # query.Comparator always must be complete


# measure definition content type class:

class MeasureDefinition(Item):
    """Metadata about a measure"""

    implements(IMeasureDefinition)

    portal_type = 'uu.formlibrary.measure'

    def __init__(self, id=None, **kwargs):
        super(MeasureDefinition, id, **kwargs)
        self._composed_queries = composed_storage()

    def site(self):
        if not getattr(self, '_v_site', None):
            self._v_site = getSite()
        return self._v_site

    def group(self):
        return aq_parent(aq_inner(self))  # folder containing

    def _source_type(self):
        return self.group().source_type

    def _metadata_field_value(self, context, path):
        if path is None:
            return NOVALUE
        return self._flex_field_value(context, path)

    def get_query(self, name):
        attr = '_v_query_%s' % name
        q = getattr(self, attr, None)
        if q is None:
            schema = IFormDefinition(self).schema
            composed = queryAdapter(self, IComposedQuery, name=name)
            if not IComposedQuery.providedBy(composed):
                return None
            q = composed.build(schema)
            if not is_query_complete(q):
                return None  # cannot perform query that is incomplete
            setattr(self, attr, q)  # cache success
        return q

    def _mr_get_value(self, context, name):
        """Get raw value for numerator or denominator"""
        assert name in ('numerator', 'denominator')
        vtype = getattr(self, '%s_type' % name, None)
        v = 1 if vtype == 'constant' else NOVALUE  # initial value
        if vtype == 'multi_metadata':
            specname = '%s_field' % name
            fieldpath = getattr(self, specname, None)
            return self._metadata_field_value(context, fieldpath)
        if vtype == 'multi_total':
            v = len(context)
        if vtype == 'multi_filter':
            q = self.get_query(name)  # gets repoze.catalog query
            if q is None:
                return NOVALUE
            # get embedded catalog for the form:
            catalog = getattr(aq_base(context), 'catalog', None)
            if catalog is None:
                return NOVALUE
            try:
                v = catalog.rcount(q)           # result count from catalog
            except (KeyError, TypeError):
                # could not perform query against catalog, likely because the
                # form in question does not have the necessary field(s), so
                # return a sentinel value safe for raw_value() to use.
                v = NOVALUE
        return v

    def _mr_values(self, context):
        """return (n, m) values for numerator, denominator"""
        n = self._mr_get_value(context, name='numerator')
        m = self._mr_get_value(context, name='denominator')
        return (n, m)

    def _flex_field_value(self, context, path):
        data = getattr(context, 'data', {})
        spec = path.split('/')
        fieldset = spec[0] if len(spec) > 1 else ''
        name = spec[1] if len(spec) > 1 else path
        record = data.get(fieldset)
        if record is not None:
            return getattr(record, name, NOVALUE)
        return NOVALUE

    def _flex_values(self, context):
        """return raw (n, m) values for numerator, denominator"""
        # inital constant / default values:
        n = m = 1
        nfield = getattr(self, 'numerator_field', None) or None
        dfield = getattr(self, 'denominator_field', None) or None
        if nfield is None and dfield is None:
            # no fields defined, NaN
            return (NOVALUE, 1)
        if nfield is not None:
            n = self._flex_field_value(context, nfield)
        if dfield is not None:
            m = self._flex_field_value(context, dfield)
        return (n, m)

    def raw_value(self, context):
        """
        Get raw value (no rounding or constant multiple), given a form
        instance.
        """
        is_multi_form = self._source_type() == MULTI_FORM_TYPE
        _div = lambda a, b: float(a) / float(b) if b else NOVALUE
        divide = lambda a, b: NOVALUE if a is None or b is None else _div(a, b)
        vfn = self._mr_values if is_multi_form else self._flex_values
        return divide(*vfn(context))

    def _normalize(self, v):
        if math.isnan(v):
            return v
        ## constant multiplier
        v = self.multiplier * v  # multiplier defaults to 1.0
        ## rounding
        rrule = self.rounding
        if rrule:
            fn = {
                'round': round,
                'ceiling': math.ceil,
                'floor': math.floor,
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
        return self._values(context)[1]

    def note_for(self, context):
        if self._source_type() == MULTI_FORM_TYPE:
            return getattr(context, 'entry_notes', None)
        # flex form:
        notesfield = getattr(self, 'notes_field', None) or None
        if notesfield:
            d = self._flex_field_value(context, notesfield)
            if d:
                return d
        return None

    def _indexed_datapoint(self, context):
        key = datapoint_cache_key(None, self, context)
        cache = DataPointCache(self.site())
        v = cache.get(key, None)
        return v and dict(v) or None

    def _datapoint(self, context):
        """uncached datapoint implementation"""
        if isbrain(context):
            context = get(context)
        n = m = None
        if (self._source_type() == MULTI_FORM_TYPE and
                self.denominator_type != 'constant'):
            n, m = self._mr_values(context)
            divide = lambda a, b: float(a) / float(b) if b else NOVALUE
            if n is None or not m:
                raw = NOVALUE
            else:
                raw = divide(n, m)
            normalized = self._normalize(raw)
        else:
            n, m = self._flex_values(context)
            raw, normalized = self._values(context)
        point_record = {
            'title': context.Title(),
            'url': context.absolute_url(),
            'path': content_path(context),
            'start': context.start,
            'value': normalized,
            'raw_value': raw,
            'display_value': self.display_format(normalized),
            'user_notes': self.note_for(context),
        }
        if n is not None:
            point_record['raw_numerator'] = n
        if m is not None:
            point_record['raw_denominator'] = m
        return point_record

    @ram.cache(datapoint_cache_key)
    def datapoint(self, context):
        """
        Returns dict for data point given form context, or
        given a catalog brain fronting for a form.
        """
        cached = self._indexed_datapoint(context)
        if cached:
            return cached
        return self._datapoint(context)

    def points(self, seq):
        """
        Given iterable seq of form instance contexts, or catalog brains
        fronting for those context, return a list of datapoints for each.
        """
        return [self.datapoint(context) for context in seq]

    def _set_cumulative_points(self, point, previous):
        """
        In place modification of point cumulative-to-present
        based on previous sorted points.
        """
        mode = getattr(self, 'cumulative', '')
        if not mode:
            return  # not cumulative, no more work to do
        opkey = getattr(self, 'cumulative_fn', 'SUM')
        cfn = AGGREGATE_FUNCTIONS.get(opkey)
        to_date = list(previous) + [point]
        _div = lambda a, b: float(a) / float(b) if b else NOVALUE
        divide = lambda a, b: NOVALUE if a is None or b is None else _div(a, b)
        if mode == 'numerator':
            key = 'raw_numerator'
            values = filter(
                lambda v: not math.isnan(v),
                [p.get(key) for p in to_date],
                )
            cnum = point['cumulative_numerator'] = cfn(values)
            val = point['value'] = self._normalize(
                divide(cnum, point.get('raw_denominator'))
                )
            point['display_value'] = self.display_format(val)
            point['user_notes'] = '%s%s' % (
                point.get('user_notes', '') or '',
                ' (cumulative numerator)',
                )
            
        return  # TODO: denominator, both, final modes

    def _cumulative_points(self, seq):
        _start = lambda o: getattr(o, 'start', None)
        start_dates = filter(lambda v: v is not None, map(_start, seq))
        series_start = min(start_dates)
        points = sorted(
            self.points(seq),
            key=lambda info: info.get('start', None),
            )  # sorted, un-normalized time-series of points
        _previous_points = lambda idx: points[:idx]
        for index, point in enumerate(points):
            point['cumulative_start'] = series_start
            previous = _previous_points(index)
            self._set_cumulative_points(point, previous)  # in-place
        return points

    def _dataset_points(self, dataset):
        if getattr(dataset, 'use_aggregate', False):
            return []
        brains = dataset.brains()
        if getattr(self, 'cumulative', None):
            return self._cumulative_points(brains)
        return self.points(brains)

    def _aggregate_dataset_points(self, aggregated, fn_name):
        """
        given a list of other aggregated datasets, get data for
        each, and calculate aggregate values for points, given
        a value aggregation function (fn).
        """
        consider = lambda o: o is not None
        fn = AGGREGATE_FUNCTIONS.get(fn_name)
        label = dict(AGGREGATE_LABELS).get(fn_name, '')
        result = []
        raw = []
        for ds in filter(consider, aggregated):
            points = self._dataset_points(ds)
            raw.append(points)
        all_points = list(chain(*raw))
        _date = lambda info: info.get('start', None)
        dates = sorted(set(map(_date, all_points)))  # de-duped ordered dates
        for d in dates:
            _hasvalue = lambda info: not math.isnan(info.get('value', NOVALUE))
            _match = lambda info: info.get('start') == d and _hasvalue(info)
            matches = filter(_match, all_points)
            if not matches:
                continue  # skip columns/dates for which no match found
            values = [info.get('value') for info in matches]
            calculated_value = fn(values)
            if math.isnan(calculated_value):
                continue
            includes = ', '.join([info.get('title') for info in matches])
            result.append({
                'title': '%s: %s' % (label, d.isoformat()),
                'url': self.absolute_url(),
                'path': '--',
                'start': d,
                'value': calculated_value,
                'user_notes': 'Aggregate value (%s) includes: %s' % (
                    label,
                    includes,
                    ),
                'display_value': self.display_format(calculated_value),
                })
        return result

    def dataset_points(self, dataset):
        """
        Given an data set specification object providing the interface
        IFormDataSetSpecification, return data points for all forms
        included in the set.
        """
        if getattr(dataset, 'use_aggregate', False):
            aggregated = getattr(dataset, 'aggregate_datasets', [])
            if aggregated:
                aggregated = [uuidToObject(ds) for ds in aggregated]
                fn_name = getattr(dataset, 'aggregate_function', 'AVG')
                return self._aggregate_dataset_points(aggregated, fn_name)
        return self._dataset_points(dataset)

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
            cumulative = info.get('cumulative_numerator', None)
            if cumulative is not None:
                op = getattr(self, 'cumulative_fn', 'SUM')
                op = '+' if op == 'SUM' else ''
                note += u'%s (%s%s) of %s' % (
                    cumulative,
                    op,
                    info.get('raw_numerator'),
                    info.get('raw_denominator'),
                    )
            else:
                if self.denominator_type != 'constant':
                    note += u'%s of %s' % (
                        info.get('raw_numerator'),
                        info.get('raw_denominator'),
                        )
                if self.denominator_type == 'multi_filter':
                    note += u' (filtered)'
                if self.denominator_type != 'multi_metadata':
                    note += u' records'
        user_notes = info.get('user_notes')
        if user_notes:
            note += ' -- %s' % user_notes
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

    def group(self):
        return aq_parent(aq_inner(self))  # folder containing

    def _source_type(self):
        return self.group().source_type

    def included_locations(self):
        """
        Returns catalog brains for each location in locations field.
        """
        catalog = getSite().portal_catalog
        spec_uids = getattr(self, 'locations', [])
        if not spec_uids:
            return None
        q = {'UID': {'query': spec_uids, 'operator': 'or', 'depth': 0}}
        return catalog.unrestrictedSearchResults(q)

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
        form_type = self._source_type()
        spec_uids = getattr(self, 'locations', [])
        if not spec_uids:
            navroot = getNavigationRoot(self)
            return {'portal_type': form_type, 'path': navroot}, []
        # first use catalog to get brains for all matches to these
        # UIDs where portal_type is form_type
        catalog = getSite().portal_catalog
        filter_q = {
            'portal_type': form_type,
            'UID': {
                'query': spec_uids,
                'operator': 'or',
                },
            }
        form_uids = [
            b.UID for b in catalog.unrestrictedSearchResults(filter_q)
            ]
        folder_uids = list(set(spec_uids).difference(form_uids))
        folder_q = {'UID': {'query': folder_uids, 'operator': 'or'}}
        folder_paths = [
            b.getPath() for b in catalog.unrestrictedSearchResults(folder_q)
            ]
        path_q = {
            'portal_type': form_type,
            'path': {
                'query': folder_paths,
                'operator': 'or',
                },
            }
        return path_q, form_uids

    def _query_spec(self):
        idxmap = {
            'query_title': 'Title',
            'query_subject': 'Subject',
            'query_state': 'review_state',
        }
        q = {}
        pathq, form_uids = self._path_query()
        if pathq is not None:
            q.update(pathq)  # include folder specified
        for name in idxmap:
            idx = idxmap[name]
            v = getattr(self, name, None)
            if isinstance(v, datetime.date):
                v = datetime.datetime(*v.timetuple()[:7])  # internal convert
            if isinstance(v, datetime.datetime):
                v = DateTime(v)
            if v:
                # only non-empty values are considered
                q[idx] = v
        if self.query_start and self.query_end:
            q['start'] = {
                'query': (DT(self.query_start), DT(self.query_end)),
                'range': 'min:max',
                }
        if self.query_start and not self.query_end:
            q['start'] = {
                'query': DT(self.query_start),
                'range': 'min',
                }
        if self.query_end and not self.query_start:
            q['start'] = {
                'query': DT(self.query_end),
                'range': 'max',
                }
        return q, form_uids

    def brains(self):
        folder_query, form_uids = self._query_spec()
        catalog = getSite().portal_catalog
        directly_specified = catalog.unrestrictedSearchResults({
            'UID': {'query': form_uids, 'operator': 'or'},
            })
        forms_in_folders_specified = catalog.unrestrictedSearchResults(
            folder_query
            )
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
        return [get(b) for b in r]

