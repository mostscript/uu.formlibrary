# module for test fixture construction -- anything that takes part within
# one or more test cases, for all else, build your common fixtures in the
# layer(s) (see layers.py), not the test cases.

import os

from plone.uuid.interfaces import IUUID
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent import ObjectCreatedEvent

import uu.formlibrary.tests as THIS_PKG


TESTS_DIR = os.path.dirname(THIS_PKG.__file__)
CHART_AUDIT_SCHEMA_FILE = os.path.join(
    TESTS_DIR,
    'sample_chart_audit_schema.xml',
    )
CHART_AUDIT_SCHEMA = open(CHART_AUDIT_SCHEMA_FILE).read().strip()


class CreateContentFixtures(object):
    """
    Adapts a test case and plone.app.testing test layer to create
    fixtures as part of a content creation test.  These fixtures
    may be reused by other test cases using the same layer.

    self.context is TestCase.
    self.layer is plone.app.testing test layer.
    self.portal is portal, set from layer.

    self.layer.fixtures_completed is flag to ensure content is created
    only once per fixture (shared state for any all instances of
    CreateContentFixtures and all cases using it).

    Call create() method to create content fixtures -- can be called by
    more than one test case, but will only create fixtures once.
    """

    def __init__(self, context, layer):
        self.context = context  # test case
        self.layer = layer
        self.portal = self.layer['portal']
        self.layer.fixtures_completed = False  # self.create() acts only once

    def _add_check(self, typename, id, iface, cls, title=None, parent=None):
        if parent is None:
            parent = self.portal
        if title is None:
            title = id
        if isinstance(title, str):
            title = title.decode('utf-8')
        parent.invokeFactory(typename, id, title=title)
        self.context.assertTrue(id in parent.contentIds())
        o = parent[id]
        self.context.assertTrue(isinstance(o, cls))
        self.context.assertTrue(iface.providedBy(o))
        o.reindexObject()
        return o  # return constructed content for use in additional testing

    def create(self):
        if self.layer.fixtures_completed:
            return  # run once, already run
        from uu.formlibrary import (
            interfaces,
            library,
            definition,
            forms,
            series,
            )
        from uu.formlibrary.measure.content import FormDataSetSpecification
        library = self._add_check(
            typename=interfaces.LIBRARY_TYPE,
            id='formlib',
            iface=interfaces.IFormLibrary,
            cls=library.FormLibrary,
            parent=self.portal,
            )
        defn = self._add_check(
            typename=interfaces.DEFINITION_TYPE,
            id='def',
            iface=interfaces.IFormDefinition,
            cls=definition.FormDefinition,
            parent=library,
            )
        field_group_a = self._add_check(   # noqa
            typename=interfaces.FIELD_GROUP_TYPE,
            id='field_group_a',
            iface=interfaces.IFieldGroup,
            cls=definition.FieldGroup,
            title=u'Field group A',
            parent=defn,
            )
        field_group_b = self._add_check(   # noqa
            typename=interfaces.FIELD_GROUP_TYPE,
            id='field_group_b',
            iface=interfaces.IFieldGroup,
            cls=definition.FieldGroup,
            title=u'Field group B',
            parent=defn,
            )
        #setspec = self._add_check(   # noqa
        #    typename=interfaces.FORM_SET_TYPE,
        #    id='form_set_query',
        #    iface=interfaces.IFormQuery,
        #    cls=FormDataSetSpecification,
        #    title=u'Form Set Query',
        #    parent=defn,
        #    )
        form_series = self._add_check(  # noqa
            typename=interfaces.SERIES_TYPE,
            id='form_series',
            iface=interfaces.IFormSeries,
            cls=series.FormSeries,
            title=u'Form series 1',
            parent=self.portal,
            )
        simple_form = self._add_check(   # noqa
            typename=interfaces.SIMPLE_FORM_TYPE,
            id='simple',
            iface=interfaces.ISimpleForm,
            cls=forms.SimpleForm,
            parent=form_series,
            )
        multi_form = self._add_check(   # noqa
            typename=interfaces.MULTI_FORM_TYPE,
            id='multi',
            iface=interfaces.IMultiForm,
            cls=forms.MultiForm,
            parent=form_series,
            )
        # fixtures for chart-audit used to test filters:
        from uu.formlibrary import search
        ca_defn = self._add_check(
            typename=interfaces.DEFINITION_TYPE,
            id='ca_defn',
            iface=interfaces.IFormDefinition,
            cls=definition.FormDefinition,
            parent=library,
            )
        ca_defn.entry_schema = CHART_AUDIT_SCHEMA
        notify(ObjectCreatedEvent(ca_defn))
        assert IUUID(ca_defn, None) is not None
        notify(ObjectModifiedEvent(ca_defn))
        ca_form = self._add_check(
            typename=interfaces.MULTI_FORM_TYPE,
            id='chartaudit',
            iface=interfaces.IMultiForm,
            cls=forms.MultiForm,
            parent=form_series,
            )
        ca_form.definition = IUUID(ca_defn)
        #filter1 = self._add_check(
        #    typename=interfaces.FILTER_TYPE,
        #    id='filter1',
        #    iface=search.interfaces.IRecordFilter,
        #    cls=search.filters.RecordFilter,
        #    parent=ca_defn,
        #    )
        #notify(ObjectCreatedEvent(filter1))
        #filter2 = self._add_check(
        #    typename=interfaces.FILTER_TYPE,
        #    id='filter2',
        #    iface=search.interfaces.IRecordFilter,
        #    cls=search.filters.RecordFilter,
        #    parent=ca_defn,
        #    )
        #notify(ObjectCreatedEvent(filter2))
        #comp_filter = self._add_check(
        #    typename=interfaces.COMPOSITE_FILTER_TYPE,
        #    id='composite',
        #    iface=search.interfaces.ICompositeFilter,
        #    cls=search.filters.CompositeFilter,
        #    parent=ca_defn,
        #    )
        #notify(ObjectCreatedEvent(comp_filter))
        #comp_filter.filter_a = IUUID(filter1)
        #comp_filter.filter_b = IUUID(filter2)
        #comp_filter.set_operator = 'difference'
        ## finally mark, don't build fixtures more than once
        self.fixtures_completed = True  # run once

