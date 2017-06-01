from Products.Archetypes.Registry import registerWidget
from plone.app.layout.navigation.root import getNavigationRootObject
try:
    from plone.app.widgets.dx import IRelatedItemsWidget
    from plone.app.widgets.dx import RelatedItemsWidget
    from plone.app.widgets.dx import RelationChoiceRelatedItemsWidgetConverter
    from plone.app.widgets.dx import DateWidget
    from plone.app.widgets.dx import DatetimeWidget
    from plone.app.widgets.at import DateWidget as ATDateWidget
    from plone.app.widgets.at import DatetimeWidget as ATDatetimeWidget
except ImportError:
    from plone.app.z3cform.widget import IRelatedItemsWidget
    from plone.app.z3cform.widget import RelatedItemsWidget
    from plone.app.z3cform.widget import RelationChoiceRelatedItemsWidgetConverter  # noqa
    from plone.app.z3cform.widget import DateWidget
    from plone.app.z3cform.widget import DatetimeWidget
    from Products.Archetypes.Widgets import DateWidget as ATDateWidget
    from Products.Archetypes.Widgets import DatetimeWidget as ATDatetimeWidget

from plone.app.widgets.utils import get_portal

from z3c.form import widget
from z3c.form.browser import text
from z3c.form.interfaces import IWidget, IFormLayer, IFieldWidget
from z3c.form.widget import FieldWidget
from zope.component import adapter, adapts
from zope.interface import implementsOnly, implementer
from zope.schema.interfaces import IBytesLine

from Products.CMFCore.utils import getToolByName

from uu.formlibrary.fields import IDescriptiveText, IDividerField


class IDescriptiveLabelWidget(IWidget):
    """marker for descriptive label widget"""


class DescriptiveLabelWidget(text.TextWidget):
    """Text-widget for which the value is hidden"""
    implementsOnly(IDescriptiveLabelWidget)


@adapter(IDescriptiveText, IFormLayer)
@implementer(IFieldWidget)
def DescriptiveLabelFieldWidget(field, request):
    """field widget factory for descriptive label"""
    return widget.FieldWidget(field, DescriptiveLabelWidget(request))


# divider field:

class IDividerWidget(IWidget):
    """marker for divider widget"""


class DividerWidget(text.TextWidget):
    """Text-widget for which the value is hidden"""
    implementsOnly(IDividerWidget)


@adapter(IDividerField, IFormLayer)
@implementer(IFieldWidget)
def DividerFieldWidget(field, request):
    """field widget factory for section divider label"""
    return widget.FieldWidget(field, DividerWidget(request))


class UIDRelatedItemsConverter(RelationChoiceRelatedItemsWidgetConverter):
    adapts(IBytesLine, IRelatedItemsWidget)

    def toWidgetValue(self, value):
        if not value:
            return self.field.missing_value
        return str(value)

    def toFieldValue(self, value):
        if not value:
            return self.field.missing_value
        return str(value)


class CustomRootRelatedWidget(RelatedItemsWidget):
    """
    This is a related items widget that allows overriding the root path.
    This can be done by sub-classing, providing a ``ComputedWigetAttribute``
    adapter for the field, or using plone.autoform.directive.widget to
    override the custom_root_query attribute.  For example::

        class IMySchema(Interface):
            my_related = RelationList(...)
            directives.widget('my_related',
                              CustomRootRelatedFieldWidget,
                              pattern_options={...},
                              custom_root_query={'portal_type': 'MyType',
                                                 'review_state': 'published'})

    """
    # Allow overrides using ComputedWidgetAttribute
    _adapterValueAttributes = (
        RelatedItemsWidget._adapterValueAttributes +
        ('custom_root_query', 'custom_root')
    )

    custom_root_query = None

    def custom_root(self):
        """Method to determine the custom root given a customizable query"""
        query = self.custom_root_query
        if not query:
            return None
        context = self.context
        portal = get_portal()
        # Start at the nav root if not already specified
        if 'path' not in query:
            nav_root = getNavigationRootObject(context, portal)
            if nav_root:
                query['path'] = {'query': '/'.join(nav_root.getPhysicalPath()),
                                 'depth': -1}

        catalog = getToolByName(portal, 'portal_catalog')
        results = catalog(**query)
        if results:
            try:
                return results[0].getPath()
            except AttributeError:
                return None

    def _base_args(self):
        args = super(CustomRootRelatedWidget, self)._base_args()
        if self.custom_root_query is not None:
            new_root = self.custom_root()
            if new_root:
                args.setdefault('pattern_options', {})['rootPath'] = new_root
        return args


@implementer(IFieldWidget)
def CustomRootRelatedFieldWidget(field, request, extra=None):
    return FieldWidget(field, CustomRootRelatedWidget(request))


class TypeADateWidget(DateWidget):
    pattern = 'type-a-date'


class TypeADatetimeWidget(DatetimeWidget):
    pattern = 'type-a-date'


class ATTypeADateWidget(ATDateWidget):
    _properties = ATDateWidget._properties.copy()
    _properties.update({
        'pattern': 'type-a-date',
        'pattern_options': {},
    })

registerWidget(
    ATTypeADateWidget,
    title='Date widget',
    description=('Date widget'),
    used_for=('Products.Archetypes.Field.DateTimeField',)
)


class ATTypeADatetimeWidget(ATDatetimeWidget):
    _properties = ATDatetimeWidget._properties.copy()
    _properties.update({
        'pattern': 'type-a-date',
        'pattern_options': {},
    })

registerWidget(
    ATTypeADatetimeWidget,
    title='Date widget',
    description=('Date widget'),
    used_for=('Products.Archetypes.Field.DateTimeField',)
)
