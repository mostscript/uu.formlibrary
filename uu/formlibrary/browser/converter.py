from z3c.form.converter import FloatDataConverter
from z3c.form.converter import FormatterValidationError
from z3c.form.interfaces import IDataConverter
from z3c.form.interfaces import IWidget
from zope.component import adapts
from zope.interface import implementer
import zope.schema


@implementer(IDataConverter)
class BetterFloatDataConverter(FloatDataConverter):

    adapts(zope.schema.interfaces.IFloat, IWidget)

    def mark(self):
        return self.formatter.symbols.get('decimal')

    def toWidgetValue(self, value):
        v = float(value)
        # does value exceed number of digits zope.i18n formatter handles
        # by default?
        return unicode(v).replace(u'.', self.mark())

    def toFieldValue(self, value):
        v = value.strip().replace(self.mark(), u'.')
        try:
            v = float(v.replace(self.mark(), '.'))
            return v
        except ValueError:
            raise FormatterValidationError(self.errorMessage, value)

