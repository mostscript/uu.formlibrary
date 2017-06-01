from plone.app.dexterity.behaviors.metadata import IPublication
from plone.app.widgets.utils import first_weekday

from uu.formlibrary.interfaces import IFormLibraryProductLayer
from uu.formlibrary.browser.widget import TypeADateWidget
from uu.formlibrary.browser.widget import TypeADatetimeWidget

from z3c.form.interfaces import IFieldWidget
from z3c.form.util import getSpecification
from z3c.form.widget import FieldWidget
from zope.component import adapter
from zope.interface import implementer

# use IDateField/IDatetimeField, not zope.schema ifaces: https://goo.gl/4hHIqB
from plone.app.z3cform.interfaces import IDateField, IDatetimeField


@adapter(IDateField, IFormLibraryProductLayer)
@implementer(IFieldWidget)
def TypeADateFieldWidget(field, request, extra=None):
    return FieldWidget(field, TypeADateWidget(request))


@adapter(IDatetimeField, IFormLibraryProductLayer)
@implementer(IFieldWidget)
def TypeADatetimeFieldWidget(field, request, extra=None):
    return FieldWidget(field, TypeADatetimeWidget(request))


@adapter(getSpecification(IPublication['effective']), IFormLibraryProductLayer)
@implementer(IFieldWidget)
def EffectiveDateFieldWidget(field, request):
    widget = FieldWidget(field, TypeADatetimeWidget(request))
    widget.pattern_options.setdefault('date', {})
    widget.pattern_options['date']['firstDay'] = first_weekday()
    return widget


@adapter(getSpecification(IPublication['expires']), IFormLibraryProductLayer)
@implementer(IFieldWidget)
def ExpirationDateFieldWidget(field, request):
    widget = FieldWidget(field, TypeADatetimeWidget(request))
    widget.pattern_options.setdefault('date', {})
    widget.pattern_options['date']['firstDay'] = first_weekday()
    return widget

