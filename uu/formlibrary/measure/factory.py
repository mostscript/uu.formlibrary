from plone.dexterity.utils import createContent, addContentToContainer
from zope.component import adapts
from zope.interface import implements

from uu.formlibrary.interfaces import MULTI_FORM_TYPE
from uu.formlibrary.search.interfaces import FILTER_TYPE
from interfaces import IMultiRecordMeasureFactory
from interfaces import MEASURE_DEFINITION_TYPE, IMeasureGroup


class MeasureFactory(object):

    implements(IMultiRecordMeasureFactory)
    adapts(IMeasureGroup)

    def __init__(self, context):
        self.context = context  # is a measure group

    def _make_measure(self, data):
        kw = {}   # field values for new measure
        naming = data.get('IMeasureWizardNaming')
        rounding = data.get('IMeasureWizardRounding')
        kw.update(naming)    # title, description, goal
        kw.update(rounding)  # rounding, display_precision, display as percent
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

