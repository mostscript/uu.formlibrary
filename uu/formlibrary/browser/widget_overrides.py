from plone.app.dexterity.behaviors.metadata import IPublication
from plone.app.textfield.interfaces import IRichText
from plone.app.widgets.utils import first_weekday
try:
    from plone.app.widgets.at_bbb import MetadataExtender
    from plone.app.widgets.dx import RichTextWidget
except ImportError:
    MetadataExtender = None
    from plone.app.z3cform.widgets import RichTextWidget

from uu.formlibrary.interfaces import IFormLibraryProductLayer
from uu.formlibrary.browser.widget import TypeADateWidget
from uu.formlibrary.browser.widget import TypeADatetimeWidget
from uu.formlibrary.browser.widget import ATTypeADatetimeWidget

from z3c.form.interfaces import IFieldWidget
from z3c.form.util import getSpecification
from z3c.form.widget import FieldWidget
from zope.component import adapter
from zope.interface import implementer
from zope.schema.interfaces import IDate
from zope.schema.interfaces import IDatetime


@adapter(IRichText, IFormLibraryProductLayer)
@implementer(IFieldWidget)
def RichTextFieldWidget(field, request):
    return FieldWidget(field, RichTextWidget(request))


@adapter(IDate, IFormLibraryProductLayer)
@implementer(IFieldWidget)
def TypeADateFieldWidget(field, request, extra=None):
    return FieldWidget(field, TypeADateWidget(request))


@adapter(IDatetime, IFormLibraryProductLayer)
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

# Monkey patch the p.a.widgets schemaextender, since overrides aren't doing
# the trick
if MetadataExtender is not None:
    MetadataExtender._old_fiddle = MetadataExtender.fiddle

    def _new_fiddle(self, schema):
        self._old_fiddle(schema)
        for field in schema.fields():
            old = field.widget

            if field.__name__ in ['startDate']:
                field.widget = ATTypeADatetimeWidget(
                    label=old.label,
                    description=old.description,
                    pattern_options={'date': {'firstDay': first_weekday()}},
                )

            if field.__name__ in ['endDate']:
                field.widget = ATTypeADatetimeWidget(
                    label=old.label,
                    description=old.description,
                    pattern_options={'date': {'firstDay': first_weekday()}},
                )

            if field.__name__ in ['effectiveDate', 'expirationDate']:
                field.widget = ATTypeADatetimeWidget(
                    label=old.label,
                    description=old.description,
                    pattern_options={'date': {'firstDay': first_weekday()}},
                )

    MetadataExtender.fiddle = _new_fiddle
