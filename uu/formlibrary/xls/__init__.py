import math
from datetime import date, datetime

import xlwt
from zope.component.hooks import getSite
from zope.interface import implements
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import ICollection

from uu.formlibrary.interfaces import IFormDefinition, IFormComponents
from uu.formlibrary.interfaces import ISimpleForm, IMultiForm
from uu.formlibrary.importexport import column_spec
from uu.formlibrary import utils

from interfaces import IFormWorkbook, IFlexFormSheet, IFieldsetGrouping
from interfaces import IBaseFormSheet

_utf8 = lambda v: v if isinstance(v, str) else v.encode('utf-8')


# convenience functions for styles:

def font_height(pt):
    return int(pt * 20)  # in 'twips' units


def set_height(row, height):
    row.height_mismatch = True
    row.height = font_height(height)


def font_name_specified(spec):
    spec = spec.split(';')
    for line in spec:
        if 'font:' in line and 'name' in line:
            return True
    return False


def font_height_specified(spec):
    spec = spec.split(';')
    for line in spec:
        if 'font:' in line and 'height' in line:
            return True
    return False


def apply_default_height(style):
    style.font.height = font_height(12)  # 12 pt


def apply_default_face(style):
    style.font.name = 'Calibri'


def xstyle(spec, **kwargs):
    r = xlwt.easyxf(spec, **kwargs)
    if not font_name_specified(spec):
        apply_default_face(r)
    if not font_height_specified(spec):
        apply_default_height(r)
    return r


# xlwt global -- set custom color names:

DEFAULT_COLORS = {
    #   name          rgb tuple             # html/hex Excel 2010 theme name
    #------------------------------------------------------------------------
    33: ('dark_blue', (31, 73, 125)),       # #1f497d, "Text 2"
    34: ('blue_accent', (79, 129, 189)),    # #4f81bd, "Accent 1"
    35: ('blue_bg', (197, 217, 241)),       # #C5D9F1, "Text 2 lighter 80%"
    36: ('purple_bg', (228, 223, 236)),     # #E4DFEC, "Accent 4 lighter 80%"
    37: ('gray_bg', (242, 242, 242)),       # #F2F2F2, "Background 1 darker 5%"
    38: ('green_bg', (235, 241, 222)),      # #EBF1DE, "Accent 3 lighter 80%"
}


FREQ_INFO = {
    'Weekly': utils.WeeklyInfo,
    'Monthly': utils.MonthlyInfo,
    'Quarterly': utils.QuarterlyInfo,
    'Annual': utils.AnnualInfo,
    'Twice monthly': utils.TwiceMonthlyInfo,
    'Every two months': utils.EveryTwoMonthsInfo,
    'Every other month': utils.EveryOtherMonthInfo,
    'Every six months': utils.SemiAnnualInfo,
    }


# ColorPalette can be used both globally, and with context
class ColorPalette(object):
    
    def __init__(self, context=None, colors=DEFAULT_COLORS):
        self.context = context  # IFormWorkbook
        self.colors = colors

    def apply(self):
        # assign name/key pair to xlwt, globally (may re-apply):
        for key, info in self.colors.items():
            name, rgb = info
            xlwt.add_palette_colour(name, key)
            if self.context is not None:
                # assign RGB to color local to workbook context:
                self.context.book.set_colour_RGB(key, *rgb)

ColorPalette().apply()   # apply DEFAULT_COLORS for use in global styles

# GLOBAL MAP OF STYLES USED (to reduce number of unique formats):
STYLES = {
    # worksheet metadata styles:
    'title': xstyle(
        'font: colour dark_blue, name Cambria, height %s; ' % font_height(18) +
        'border: bottom thick;'
        'alignment: vertical center;'
        'pattern: pattern solid, fore_colour green_bg;'
        ),
    'description': xstyle(
        'font: colour gray50, height %s;' % font_height(11) +
        'alignment: vertical top, wrap True;'
        ),
    'sourcelink': xstyle('font: name Arial Narrow, colour blue_accent'),
    'modified': xstyle('font: colour green'),
    'statuslabel': xstyle(
        'font: colour violet; '
        'alignment: horizontal right;'
        ),
    'statusvalue': xstyle(
        'font: colour violet, bold True; '
        'alignment: horizontal center;'
        ),
    'reportingdate': xstyle(
        'font: colour blue; '
        'alignment: horizontal center; ',
        num_format_str='MM/dd/yyyy'
        ),
    # field group / data styles:
    'grouptitle': xstyle(
        'font: height %s, bold true; ' % font_height(18) +
        'pattern: pattern solid, fore_colour blue_bg;'
        'border: bottom thick;'
        'alignment: vertical center;'
        ),
    'fieldname_odd': xstyle(
        'alignment: vertical center; '
        'pattern: pattern solid, fore_colour purple_bg; '
        'font: name Arial Narrow, colour gray50, height %s;' % font_height(9),
        ),
    'fieldname_even': xstyle(
        'alignment: vertical center; '
        'pattern: pattern solid, fore_colour gray_bg; '
        'font: name Arial Narrow, colour gray50, height %s;' % font_height(9),
        ),
    'fieldtitle_odd': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour purple_bg; '
        ),
    'fieldtitle_even': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour gray_bg; '
        ),
    'fieldvalue_odd': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour purple_bg; '
        ),
    'fieldvalue_odd_date': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour purple_bg; ',
        num_format_str='MM/dd/yyyy'
        ),
    'fieldvalue_even': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour gray_bg; '
        ),
    'fieldvalue_even_date': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour gray_bg; ',
        num_format_str='MM/dd/yyyy'
        ),
    # multi-record form styles:
    'fieldname_multi': xstyle(
        'alignment: vertical center; '
        'font: name Arial Narrow, colour gray50, height %s;' % font_height(9),
        ),
    'fieldtitle_multi': xstyle(
        'font: colour dark_blue, bold True; '
        'alignment: vertical center, wrap true; '
        ),
    'fieldvalue_multi': xstyle(
        'alignment: vertical center, wrap true; '
        ),
    'fieldvalue_multi_date': xstyle(
        'alignment: vertical center, wrap true; '
        'pattern: pattern solid, fore_colour gray_bg; ',
        num_format_str='MM/dd/yyyy'
        ),
    }


def base_title(context):
    freq = context.frequency
    infocls = FREQ_INFO[freq]
    base = infocls(context.start).title
    base = base.replace('Week beginning', 'From')
    base = base.replace('Period beginning', 'From')
    base = base.replace('Period ending', 'To')
    base = base.replace('Week ending', 'To')
    return base


def sheet_name(context, already_used=()):
    result = title = context.title
    if len(title) > 28:
        base = base_title(context)
        parts = [part.strip() for part in title.split('-')]
        numparts = len(parts)
        result = base
        if numparts == 2:
            part = parts[0] if parts[0] != base else parts[-1]
            result = u', '.join((base, part))[:31]
        if numparts >= 3:
            suffix = parts[-1]
            result = u', '.join((base, suffix))[:31]
    # avoid duplication, if we have a sequence of already used titles:
    i = 1
    while result in already_used:
        result = u'-'.join((result[:28], str(i)))
        i += 1
    return result


class FormWorkbook(object):

    implements(IFormWorkbook)

    def __init__(self, stream):
        if isinstance(stream, basestring):
            # filename
            self.stream = open(_utf8(stream), 'wb')
        else:
            self.stream = stream
        self.sheets = []
        self.names = []   # track this to avoid dupe names
        self.book = xlwt.Workbook()
        self.set_defaults()

    def set_defaults(self):
        # set default workbook styles:
        xlwt.Style.default_style.font.size = 20 * 12  # 10 pt
        xlwt.Style.default_style.font.name = 'Calibri'
        # adapt, set color palette:
        self.palette = ColorPalette(self)
        self.palette.apply()

    def save(self):
        if getattr(self.stream, 'closed', False):
            raise ValueError('Cannot save stream, it is closed.')
        self.stream.seek(0)
        self.stream.truncate(0)
        self.book.save(self.stream)

    def add(self, form):
        if ISimpleForm.providedBy(form):
            form_sheet = FlexFormSheet(form, self)
            self.sheets.append(form_sheet)
            return form_sheet
        if IMultiForm.providedBy(form):
            form_sheet = MultiRecordFormSheet(form, self)
            self.sheets.append(form_sheet)
            return form_sheet

    def close(self):
        self.stream.close()


class BaseFormSheet(object):

    implements(IBaseFormSheet)

    columns = 4
    colwidth = 30
    meta_merge_multiplier = 1

    def __init__(self, context, workbook):
        if not IFormWorkbook.providedBy(workbook):
            raise TypeError('Incorrect workbook type')
        self.context = context
        self.workbook = workbook
        self.worksheet = None
        self._definition = None
        self.reset()

    @property
    def cursor(self):
        return self._cursor

    def definition(self):
        if self._definition is None:
            self._definition = IFormDefinition(self.context)
        return self._definition

    def write(self):
        self.reset()
        self.write_metadata()
        self.write_data()
        self.workbook.save()

    def reset(self):
        if self.worksheet is None:
            name = sheet_name(self.context, self.workbook.names)
            self.worksheet = self.workbook.book.add_sheet(name)
            self.workbook.names.append(name)
        sheet = self.worksheet
        self._cursor = 0
        # column widths for sheet to 30.0
        for i in range(self.columns):
            sheet.col(i).width = 256 * self.colwidth

    def _description(self):
        context = self.context
        defn = self.definition()
        description = context.description or defn.description
        if description:
            return description.strip()
        return None

    def status(self):
        tool = getSite().portal_workflow
        chain = tool.getChainFor(self.context)[0]
        wdefn = tool.get(chain)
        status = tool.getStatusOf(chain, self.context)['review_state']
        return wdefn.states[status].title

    def write_metadata(self):
        sheet = self.worksheet
        # Title cell content, style @ A1:D1 merged
        set_height(sheet.row(0), 40)
        title = self.context.title.strip()
        rightside = 4 * self.meta_merge_multiplier - 1  # column D or equiv
        sheet.write_merge(0, 0, 0, rightside, title, STYLES.get('title'))
        desc = self._description()
        if desc:
            set_height(sheet.row(1), 12 * (math.ceil(len(desc) / 120.0) + 1))
            sheet.write_merge(
                1, 1, 0, rightside, desc,
                STYLES.get('description')
                )
        # URL as hyperlink at A3:D3
        url = self.context.absolute_url()
        url_formula = 'HYPERLINK("%s";"%s")' % (url, 'Source: %s' % url)
        style = STYLES.get('sourcelink')
        sheet.write_merge(2, 2, 0, rightside, xlwt.Formula(url_formula), style)
        # Modified at merged A5:B5
        modified = self.context.modified().asdatetime().isoformat(' ')[:19]
        style = STYLES.get('modified')
        sheet.write_merge(4, 4, 0, 1, 'Last modified: %s' % modified, style)
        # Form status label at C5, status (title, not id) at D5
        sheet.write(4, 2, 'Form status:', STYLES.get('statuslabel'))
        sheet.write(4, 3, self.status(), STYLES.get('statusvalue'))
        # start, end date for form on line 6
        sheet.write(5, 0, 'Reporting from:')
        sheet.write(5, 1, self.context.start, STYLES.get('reportingdate'))
        sheet.write(5, 2, 'to')
        sheet.write(5, 3, self.context.end, STYLES.get('reportingdate'))

    def write_data(self):
        raise NotImplementedError('abstract')


class FlexFormSheet(BaseFormSheet):

    implements(IFlexFormSheet)

    def __init__(self, context, workbook):
        if not ISimpleForm.providedBy(context):
            raise TypeError('Incorrect context, must provide ISimpleForm')
        super(FlexFormSheet, self).__init__(context, workbook)
        self._groups = None

    def groups(self):
        if self._groups is None:
            definition = self.definition()
            components = IFormComponents(definition)
            names = components.names
            groups = components.groups
            # default fieldset schema provider is definition itself:
            self._groups = [definition]
            # other fieldsets:
            self._groups += [groups.get(name) for name in names]
            # filter removing any empty fieldsets:
            _nonempty = lambda group: bool(getFieldsInOrder(group.schema))
            self._groups = filter(_nonempty, self._groups)
        return self._groups

    def write_data(self):
        # set cursor for content, with a spacing row below metadata above
        self._cursor = 7  # row number 8
        for group in self.groups():
            grouping = FieldSetGrouping(self, group, self._cursor)
            grouping.write()
            self._cursor += 1   # spacer row


class MultiRecordFormSheet(BaseFormSheet):

    defstyle = STYLES.get('fieldvalue_multi')
    datestyle = STYLES.get('fieldvalue_multi_date')
    colwidth = 15
    meta_merge_multiplier = 2  # stretch merge on metadata twice as wide

    def __init__(self, context, workbook):
        if not IMultiForm.providedBy(context):
            raise TypeError('Incorrect context, must provide IMultiForm')
        super(MultiRecordFormSheet, self).__init__(context, workbook)
        self.schema = self.definition().schema
        self.columns = len(getFieldsInOrder(self.schema))

    def write_row(self, rowidx, record, colspec):
        colidx = 0
        for name, col in colspec:
            style = self.datestyle if col.isdate else self.defstyle
            self.worksheet.write(rowidx, colidx, col.get(record), style)
            colidx += 1

    def write_data(self):
        sheet = self.worksheet
        # set cursor for content, with a spacing row below metadata above
        self._cursor = 7  # row number 8
        # TODO: transform CSV
        colspec = column_spec(self.context, self.schema, dialect='xlwt')
        # write out header rows for fieldname, title column headings
        colidx = 0
        for name, col in colspec:
            title = col.title
            r1, r2 = self._cursor, self._cursor + 1
            sheet.write(r1, colidx, name, STYLES.get('fieldname_multi'))
            sheet.write(r2, colidx, title, STYLES.get('fieldtitle_multi'))
            colidx += 1
        self._cursor += 2  # two rows written above
        # Iterate through records, and write values for each column
        for record in self.context.values():
            self.write_row(self._cursor, record, colspec)
            self._cursor += 1
        # finally, set up freeze panes at row 9:
        sheet.set_panes_frozen(True)
        sheet.set_horz_split_pos(9)
        sheet.set_remove_splits(True)


class FieldSetGrouping(object):

    implements(IFieldsetGrouping)

    def __init__(self, worksheet, group, origin):
        primary = IFormDefinition.providedBy(group)
        self.worksheet = worksheet          # IFormWorksheet
        self.context = worksheet.context    # ISimpleForm
        self.group = group
        data = self.context.data
        self.data = data.get('') if primary else data.get(self.group.getId())
        self.field_schema = group.schema
        self.title = u'Primary fields' if primary else group.title
        self.origin = origin        # origin/start row
        self.size = 0
        self.cursor = self.origin

    def write(self):
        self.reset()
        self.write_metadata()
        self.write_data()
        self.worksheet._cursor = self.cursor

    def reset(self):
        sheet = self.worksheet.worksheet
        start = self.origin
        end = self.origin + (self.size - 1)
        for rowidx in range(start, end + 1):
            row = sheet.row(rowidx)
            for colidx in range(0, 4):
                row.set_cell_blank(colidx)

    def write_metadata(self):
        sheet = self.worksheet.worksheet
        style = STYLES.get('grouptitle')
        sheet.write_merge(self.origin, self.origin, 0, 3, self.title, style)
        self.cursor += 1
        self.size += 1

    def is_multiple(self, field, value):
        return ICollection.providedBy(field) and len(value) > 1

    def use_dateformat(self, field, value):
        if isinstance(value, date) or isinstance(value, datetime):
            return True
        return False

    def write_data(self):
        usegrid = getattr(self.group, 'group_usage', None) == 'grid'
        sheet = self.worksheet.worksheet
        idx = 0
        odd = lambda v: bool(v % 2)
        if usegrid:
            data = getattr(self.data, 'data', []) or []
        else:
            data = [self.data]
        rowidx = 0
        for record in data:
            rowidx += 1
            for fieldname, field in getFieldsInOrder(self.field_schema):
                # get title, value
                title = field.title
                if usegrid:
                    value = record.get(fieldname, '')
                else:
                    value = getattr(record, fieldname, '')
                # get row color (zebra):
                idx += 1  # repeat / zebra stripe index
                oddrow = odd(idx)
                # computed row height based on length of the title:
                lines = int(math.ceil(len(title) / 67.0))
                set_height(sheet.row(self.cursor), 18 * lines)
                if usegrid:
                    # include row number in fieldname col, grouped zebra stripe
                    fieldname = 'ROW-%s: %s' % (rowidx, fieldname)
                    oddrow = odd(rowidx)
                # field name:
                _style = 'fieldname_odd' if oddrow else 'fieldname_even'
                style = STYLES.get(_style)
                sheet.write(self.cursor, 0, fieldname, style)
                # field title:
                _style = 'fieldtitle_odd' if oddrow else 'fieldtitle_even'
                style = STYLES.get(_style)
                sheet.write_merge(self.cursor, self.cursor, 1, 2, title, style)
                # write field value(s):
                _style = 'fieldvalue_odd' if oddrow else 'fieldvalue_even'
                if self.use_dateformat(field, value):
                    _style = '_'.join((_style, 'date'))
                style = STYLES.get(_style)
                # collection field with more than one answer:
                if not self.is_multiple(field, value):
                    value = [value]
                vidx = 0
                for element in value:
                    if isinstance(element, basestring) and len(element) > 30:
                        # word-wrap likely necessary, compute row height:
                        lines = max(lines, int(math.ceil(len(element) / 30.0)))
                        set_height(sheet.row(self.cursor), 18 * lines)
                    if vidx:
                        for i in range(0, 3):
                            sheet.write(self.cursor, i, '', style)
                    sheet.write(self.cursor, 3, element, style)
                    self.cursor += 1
                    vidx += 1

