import csv
from zope.component import adapter
from zope.interface import implements, implementer
from StringIO import StringIO
from zope import schema
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import IDate, IDatetime

from uu.formlibrary.interfaces import IMultiForm, ICSVColumn, IMultiFormCSV


_str = lambda v: v.encode('utf-8') if isinstance(v, unicode) else str(v)


def multi_column_fields(fields, form):
    """
    Return a dict with the number of columns per field...
    This is usually 1, but may, in the context of some record in the
    form, be more for a List (multiple choice) field.
    """
    selected = {}
    for name, field in fields:
        selected[name] = set()
        for record in form.values():
            val = getattr(record, name, None)
            if type(val) in (list, tuple, set):
                selected[name].update(val)
            else:
                continue  # ignore non-sequence (e.g. None) valuea
        for ignore_value in ['', None]:
            if ignore_value in selected[name]:
                selected[name].remove(ignore_value)
    # return key, count of union of unique values (justifying column-per):
    return dict([(k, len(v)) for k, v in selected.items() if len(v) > 1])


class CSVColumn(object):
    implements(ICSVColumn)

    def __init__(self, field, index=None, dialect='csv'):
        self.field = field
        self.index = index
        self.multiple = self._is_multiple()
        if self.multiple:
            self.sortspec = [t.value for t in field.value_type.vocabulary]
        self.name = self._name()
        self.title = self._title()
        self.dialect = dialect
        self.isdate = IDate.providedBy(field) or IDatetime.providedBy(field)

    def _is_multiple(self):
        return (
            schema.interfaces.IList.providedBy(self.field) or
            schema.interfaces.ISet.providedBy(self.field) or
            schema.interfaces.ITuple.providedBy(self.field)
            )

    def _name(self):
        name = self.field.__name__
        if not self.multiple or not self.index:
            return name  # not multiple or zero-indexed column==omit
        return '%s_%s' % (name, self.index + 1)  # 0-index -> label

    def _title(self):
        if not self.multiple or not self.index:
            return self.field.title    # not multiple, zero-indexed col==omit
        return '(%s) %s' % (self.index + 1, self.field.title)  # 0-index->label

    def normalize(self, value):
        if isinstance(value, bool):
            value = 'Yes' if value else 'No'  # T/F to yes/no
        if self.dialect == 'xlwt':
            return value
        return _str(value)  # for CSV, normalize everything to str

    def get(self, record):
        fieldname = self.field.__name__
        v = getattr(record, fieldname, '')
        if v is None:
            return ''
        if not self.multiple:
            return self.normalize(v)
        # mutliple-valued field types - no one-to-one value :
        idx = self.index or 0  # if None
        try:
            possible = self.sortspec[idx]
            if possible in v:
                # possible choice was chosen:
                return self.normalize(possible)
            else:
                return ''  # empty cell
        except IndexError:
            return ''


def column_spec(form, schema, dialect='csv'):
    """Return list of (name, CSVColumn instance) tuples"""
    fields = getFieldsInOrder(schema)
    multi_fields = multi_column_fields(fields, form)
    colspec = []
    for name, field in fields:
        if name in multi_fields:
            for idx in range(multi_fields[name]):
                col = CSVColumn(field, idx, dialect=dialect)
                colspec.append((col.name, col))
        else:
            colspec.append((name, CSVColumn(field, dialect=dialect)))
    return colspec


@adapter(IMultiForm)
@implementer(IMultiFormCSV)
def csv_export(form, schema=None):
    """
    For a record container form, get all contained record values, and
    write to CSV according to the form.schema or schema provided.

    If any field has multiple values, represent multiple columns for that
    field, one column for each sequence value, allocating up to the number
    of columns needed for actual data, but no more.
    """
    if schema is None:
        schema = getattr(form, 'schema', None)
        if schema is None:
            raise ValueError('improper or no schema provided')
    out = StringIO()
    colspec = column_spec(form, schema)
    colnames = zip(*colspec)[0]
    writer = csv.DictWriter(out, colnames)
    # write first row: column names:
    writer.writerow(dict([(n, n) for n in colnames]))
    # write next row: column titles
    writer.writerow(dict([(name, col.title.encode('utf-8'))
                          for name, col in colspec]))
    for record in form.values():
        record_dict = {}
        for name, col in colspec:
            record_dict[name] = col.get(record)
        writer.writerow(record_dict)
    out.seek(0)
    return out.read()

