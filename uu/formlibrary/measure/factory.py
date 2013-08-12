from plone.dexterity.utils import createContent, addContentToContainer
from zope.component import adapts
from zope.interface import implements

from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from uu.formlibrary.search.interfaces import FILTER_TYPE
from interfaces import IMultiRecordMeasureFactory
from interfaces import MEASURE_DEFINITION_TYPE, IMeasureGroup


class MeasureFactory(object):

    implements(IMultiRecordMeasureFactory)
    adapts(IMeasureGroup)

    def __init__(self, context):
        self.context = context  # is a measure group

    def data_implies_percentage(self, saved_formdata):
        if self.context.source_type == SIMPLE_FORM_TYPE:
            d = saved_formdata.get('IMeasureWizardFlexFields', {})
            n, d = d.get('numerator_field'), d.get('denominator_field')
            return bool(n) and bool(d)  # both defined
        d = saved_formdata.get('IMeasureWizardMRCriteria', {})
        nt, mt = d.get('numerator_type', None), d.get('denominator_type', None)
        return (
            nt in ('multi_filter', 'mutli_metadata') and
            mt in ('multi_total', 'multi_filter', 'multi_metadata')
            )

    def _make_measure(self, data):
        kw = {}   # field values for new measure
        # use defaults for rounding, display_precision, infer if percentage
        kw.update({
            'rounding': '',
            'display_precision': 1,
            'express_as_percentage': self.data_implies_percentage(data),
            })
        if self.context.source_type == MULTI_FORM_TYPE:
            calc = data.get('IMeasureWizardMRCriteria')
        else:
            calc = data.get('IMeasureWizardFlexFields')  # flex form
        kw.update(calc)  # mr: numerator/denominator types; flex: fields
        measure = createContent(MEASURE_DEFINITION_TYPE, **kw)
        if kw.get('express_as_percentage', False):
            measure.multiplier = 100.0
            measure.value_type = 'percentage'
        else:
            measure.value_type = 'count'
        addContentToContainer(self.context, measure)  # will auto-choose id
        return measure.__of__(self.context)

    def _make_filter(self, measure, name):
        kw = {}   # field values for new measure
        kw['title'] = name
        rfilter = createContent(FILTER_TYPE, **kw)
        addContentToContainer(measure, rfilter)  # will auto-choose id

    def _make_filters(self, measure, data):
        calc = data.get('IMeasureWizardMRCriteria')
        num_type = calc.get('numerator_type')
        den_type = calc.get('denominator_type')
        if num_type == 'multi_filter':
            self._make_filter(measure, name=u'Numerator')
        if den_type == 'multi_filter':
            self._make_filter(measure, name=u'Denominator')

    def __call__(self, data):
        """Given wizard data, create measure"""
        measure_definition = self._make_measure(data)
        if self.context.source_type == MULTI_FORM_TYPE:
            self._make_filters(measure_definition, data)
        return measure_definition

