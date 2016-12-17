from plone.dexterity.utils import createContent, addContentToContainer
from zope.component import adapts
from zope.interface import implements

from uu.formlibrary.interfaces import SIMPLE_FORM_TYPE, MULTI_FORM_TYPE
from interfaces import IMultiRecordMeasureFactory, IMeasureGroup
from interfaces import MEASURE_DEFINITION_TYPE, MR_FORM_COMMON_FILTER_CHOICES


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
        non_constant = [term.value for term in MR_FORM_COMMON_FILTER_CHOICES]
        return nt in non_constant and mt in non_constant

    def _make_measure(self, data):
        kw = {}   # field values for new measure
        # use defaults for rounding, display_precision, infer if percentage
        use_pct = self.data_implies_percentage(data)
        kw.update({
            'rounding': '',
            'display_precision': 1 if use_pct else 0,
            'express_as_percentage': use_pct,
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

    def __call__(self, data):
        """Given wizard data, create measure"""
        measure_definition = self._make_measure(data)
        return measure_definition

