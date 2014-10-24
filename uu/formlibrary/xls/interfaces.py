from zope.interface import Interface
from zope.interface.interfaces import IInterface
from zope import schema

from uu.formlibrary.interfaces import ISimpleForm


class IFormWorkbook(Interface):
    """
    Object representing a workbook for one or more form worksheets.
    Should be constructed with a filename or file-stream object.
    """
    
    book = schema.Object(
        schema=Interface,  # xltw.Workbook object
        )

    stream = schema.Object(
        schema=Interface,  # file-like object
        )

    sheets = schema.List(
        value_type=schema.Object(schema=Interface)  # of IFlexFormSheet obj
        )

    def save():
        """Save workbook to stream; call self.book.save(self.stream)"""

    def add(form):
        """
        Add a form, creates a form sheet object, appends to self.sheets,
        returns form-sheet (adapter) object.
        """

    def close():
        """Close stream"""


class IFlexFormSheet(Interface):
    """
    Object representing an excel worksheet, multi-adapts flex form and
    IFormWorkbook object.
    """

    context = schema.Object(
        schema=ISimpleForm,
        )

    workbook = schema.Object(
        title=u'IFormWorkbook object containing this sheet.',
        schema=IFormWorkbook,
        )

    worksheet = schema.Object(
        schema=Interface,  # xlwt.Worksheet object
        )

    cursor = schema.Int(
        title=u'Read-only cursor of current row',
        description=u'Implementations internally write state for this.',
        readonly=True,
        )

    def definition():
        """Get form definition for flex form contex."""

    def groups():
        """
        Return field groups for form definition bound to flex form
        context.
        """

    def write():
        """
        Write all metadata, then all fieldsets; output should be styled.
        """

    def write_metadata():
        """Make rows for title, description, other metadata; style them."""

    def write_data():
        """For each fieldset, in order, write each to sheet."""

    def reset():
        """
        Clear all cells in sheet; may replace self.worksheet.
        """


class IFieldsetGrouping(Interface):
    """
    Object for output of fieldset / group to sheet, should be a
    multi-adapter of worksheet, field group, mapping of source data.

    This interface keeps state that should not be concurrently modified.
    """

    # READ-ONLY PROPERTIES:
    title = schema.TextLine(
        title=u'Field group title (computed)',
        readonly=True,
        )

    field_schema = schema.Object(
        title=u'Field group schema (computed)',
        schema=IInterface,
        readonly=True,
        )

    size = schema.Int(
        title=u'Size, row height',
        description=u'Computed row height for grouping, including title row; '
                    u'this is calculated based on number of distinct values '
                    u'for all fields in field schema.',
        readonly=True,
        )

    origin = schema.Int(
        title=u'Origin row (title row)',
        )

    cursor = schema.Int(
        title=u'Read-only cursor of current row',
        description=u'Implementations internally write state for this.',
        readonly=True,
        )

    def write():
        """
        Write entire fieldset to sheet, style it.
        """

    def write_metadata():
        """Make header row, write title to it, style it."""

    def write_data():
        """For each field, get all values, write rows, apply styles."""

    def reset():
        """
        Clear all cells used for field group, and reset cursor to origin.
        """

