from z3c.form import widget
from z3c.form.browser import text
from zope.component import adapter
from zope.interface import implementsOnly, implementer
from z3c.form.interfaces import IWidget, IFormLayer, IFieldWidget

from uu.formlibrary.fields import IDescriptiveText


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

