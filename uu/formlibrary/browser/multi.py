import json
import uuid

from plone.autoform.form import AutoExtensibleForm
from plone.autoform.interfaces import OMITTED_KEY
from plone.autoform.utils import mergedTaggedValuesForForm
from plone.memoize import ram
from z3c.form import form, field
from z3c.form.interfaces import IDataConverter
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.interface import alsoProvides
from zope.pagetemplate.interfaces import IPageTemplate
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import ICollection
from zope.component.hooks import getSite
from zope.component import getMultiAdapter
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from Products.statusmessages.message import _utf8

from uu.workflows.utils import history_log

from uu.formlibrary.forms import ComposedForm, common_widget_updates

from common import BaseFormView


ROW_TEMPLATE = ViewPageTemplateFile('row.pt')
DIV_TEMPLATE = ViewPageTemplateFile('formdiv.pt')

marker = object()


def converter_cache_key(method, self, name, value):
    return (self.definition.signature, name, value)


def unicode_unwrap(value):
    """
    Unwrap unwanted excess unicode escaping in a basestring value by repeated
    decoding with 'unicode-escape' codec, until it fails to decode.
    """
    if type(value) is str:
        value = value.decode('utf-8')
    try:
        value = value.decode('unicode-escape')
        if any(map(lambda c: ord(c) > 127, value)):
            return unicode_unwrap(value)
    except UnicodeEncodeError:
        pass
    return value


class MetadataForm(ComposedForm):
    template = ViewPageTemplateFile('metadata_form.pt')

    def __init__(self, context, request):
        super(MetadataForm, self).__init__(
            context,
            request,
            name='metadata',
            )


class RowForm(AutoExtensibleForm, form.EditForm):

    template = ROW_TEMPLATE
    schema = None  # override property so we can set attr below

    def __init__(self, record, schema, request):
        self._rowform_rec = record
        self.schema = schema
        self.prefix = '%s~' % record.record_uid  # (js should split on '~')
        super(RowForm, self).__init__(record, request)

    def updateWidgets(self):
        common_widget_updates(self)
        super(RowForm, self).updateWidgets()


class DivRowForm(RowForm):
    template = DIV_TEMPLATE


class RowDisplayForm(form.DisplayForm):

    template = ROW_TEMPLATE

    def __init__(self, record, schema, request):
        self.fields = field.Fields(schema)
        super(RowDisplayForm, self).__init__(record, request)

    def updateWidgets(self):
        common_widget_updates(self)
        super(RowDisplayForm, self).updateWidgets()


class DivRowDisplayForm(RowDisplayForm):
    template = DIV_TEMPLATE


class MultiFormEntry(BaseFormView):

    def __init__(self, context, request):
        super(MultiFormEntry, self).__init__(context, request)
        self._fields = []
        self._schema = None
        self._status = IStatusMessage(self.request)
        self.has_metadata = bool(self.definition.metadata_definition)
        if self.has_metadata:
            self.mdform = MetadataForm(context, request)
            if self.VIEWNAME != 'edit':
                self.mdform.mode = 'display'

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)  # index() via Five/framework magic

    def update(self, *args, **kwargs):
        if not kwargs.get('saveonly', False):
            self._init_baseform()
        msg = ''
        if 'payload' in self.request.form:
            # strip out double-escaping of unicode (ugly):
            json = self.request.form.get('payload').strip()
            if json:
                json = unicode_unwrap(json)
                oldkeys = self.context.keys()
                # save the data payload to records, also notifies
                # ObjectModifiedEvent, if data is modified, which
                # will result in reindexing embedded catalog used
                # by measures:
                self.context.update_all(json)
                newkeys = self.context.keys()
                count_new = len(set(newkeys) - set(oldkeys))
                count_updated = len(set(oldkeys) & set(newkeys))
                count_removed = len(set(oldkeys) - set(newkeys))
                msg = 'Data has been saved. '
                if count_new or count_updated or count_removed:
                    msg += '('
                if count_new:
                    msg += ' %s new entries. ' % count_new
                if count_updated:
                    msg += ' %s updated entries. ' % (
                        count_updated,)
                if count_removed:
                    msg += ' %s removed entries. ' % (
                        count_removed,)
                if count_new or count_updated or count_removed:
                    msg += ')'
                history_log(self.context, msg)
                if 'save_submit' in self.request.form:
                    wftool = getToolByName(self.context, 'portal_workflow')
                    chain = wftool.getChainFor(self.context)[0]
                    state = wftool.getStatusOf(chain,
                                               self.context)['review_state']
                    if state == 'visible':
                        wftool.doActionFor(self.context, 'submit')
                        self.context.reindexObject()
                        msg += ' (form submitted for review)'
                        if not kwargs.get('saveonly', False):
                            url = self.context.absolute_url()
                            self.request.RESPONSE.redirect(url)
            if self.has_metadata:
                self.mdform.update()
                md_msg = 'Saved metadata fields on multi-record form.'
                self.mdform._handleSave(None, msg=md_msg)
        if msg:
            self._status.addStatusMessage(msg, type='info')

    @property
    def schema(self):
        if not self._schema:
            entry_uids = self.context.keys()
            if not entry_uids:
                self._schema = self.definition.schema
            else:
                # use schema of first contained record
                self._schema = self.context[entry_uids[0]].schema
        return self._schema

    def fields(self):
        if not self._fields:
            fields = getFieldsInOrder(self.schema)
            omitted = mergedTaggedValuesForForm(
                self.schema,
                OMITTED_KEY,
                self.baseform).keys()
            self._fields = [(k, v) for (k, v) in fields if k not in omitted]
        return [v for k, v in self._fields]  # field objects

    def fieldnames(self):
        if not self._fields:
            self._fields = getFieldsInOrder(self.schema)
        return [k for k, v in self._fields]  # field objects

    def logourl(self):
        filename = getattr(self.definition.logo, 'filename', None)
        if filename is None:
            return None
        base = self.definition.absolute_url()
        return '%s/@@download/logo/%s' % (base, filename)

    def metadata_form(self):
        """render metadata form, if available; used by template"""
        if not self.has_metadata:
            return ''
        self.mdform.update()
        return self.mdform.render()

    def instructions(self):
        _instructions = getattr(self.definition, 'instructions')
        if not _instructions:
            return u''
        return getattr(_instructions, 'output', None) or u''

    def portalurl(self):
        return getSite().absolute_url()

    def classname(self, name):
        """
        class name is two names separated by space: column number prefixed
        by the letter 'c' and column name prefixed by 'col-'
        """
        if not isinstance(name, basestring):
            name = name.__name__  # assume field, not fieldname
        fieldnames = self.fieldnames()
        if name not in fieldnames:
            return 'c0 col-%s' % name
        return 'c%s col-%s' % (fieldnames.index(name), name)

    def entry_uids(self):
        if not hasattr(self.context, '_keys'):
            self._keys = self.context.keys()  # ordered uids of entries
        return self._keys

    def _init_baseform(self):
        """
        Initialize base form for re-use * N rows to avoid re-construction;
        should be called by self.update(), just once.
        """
        row_views = {
            ('edit', 'Stacked'): DivRowForm,
            ('view', 'Stacked'): DivRowDisplayForm,
            ('edit', 'Columns'): RowForm,
            ('view', 'Columns'): RowDisplayForm,
        }
        row_view_cls = row_views[(self.VIEWNAME, self.displaymode)]
        self.dummy_record = self.context.create()
        alsoProvides(self.dummy_record, self.schema)
        self.baseform = row_view_cls(
            self.dummy_record,
            self.schema,
            self.request
            )
        self.baseform.update()
        # create a mapping of data converters by fieldname
        self.converters = {}    # fieldname to converter
        self.defaults = {}      # fieldname to default value
        for fieldname in self.baseform.fields:
            widget = self.baseform.widgets[fieldname]
            field = self.schema[fieldname]
            self.converters[fieldname] = IDataConverter(widget)
            self.defaults[fieldname] = field.default
            # lookup template once, bind -- to avoid repeated lookup
            widget.template = getMultiAdapter(
                (
                    widget.context,
                    self.request,
                    self.baseform,
                    field,
                    widget
                ),
                IPageTemplate,
                name=widget.mode
                )
        self.baseform.render()  # force chameleon compilation here

    def fix_item_values(self, items, value):
        vtype = type(value)
        for item in items:
            if vtype in (set, list):
                # multi-choice  (checkbox)
                item['checked'] = (item.get('value', marker) in value)
            elif vtype is bool:
                # compare vs. string repr of boolean value
                _item_value = True if item.get('value') == 'true' else False
                item['checked'] = (_item_value == value)
            else:
                # single-choice (radio/select)
                item['checked'] = (value == item.get('value', marker))

    @ram.cache(converter_cache_key)
    def toWidgetValue(self, fieldname, value):
        converter = self.converters[fieldname]
        if value == '--NOVALUE--':
            value = None
        return converter.toWidgetValue(value)

    def _values(self, record, fieldname):
        """returns raw, widget values as tuple"""
        default = self.defaults.get(fieldname, None)
        value = getattr(record, fieldname, default)
        return value, self.toWidgetValue(fieldname, value)

    def apply_values(self, record):
        for fieldname, widget in self.baseform.widgets.items():
            value, widget.value = self._values(record, fieldname)
            if type(getattr(widget, 'items', None)) is list:
                self.fix_item_values(widget.items, value)

    def rowform(self, uid=None):
        """
        optimized row form re-uses same baseform, applying values and
        identity/name in place.  This avoids constructing new form and
        associated widgets, converters, etc.
        """
        if uid is None or uid not in self.entry_uids():
            record = self.context.create()  # create new with UUID
        else:
            record = self.context.get(uid)
        self._last_uid = record.record_uid
        self.apply_values(record)
        orig_html = self.baseform.render()
        dummy_uid = self.dummy_record.record_uid
        return orig_html.replace(dummy_uid, record.record_uid)

    def last_row_uid(self):
        """return the last row uid for row rendered by rowform or random"""
        if hasattr(self, '_last_uid'):
            return self._last_uid
        return str(uuid.uuid4())  # default random UUID is fallback only

    def new_row_url(self):
        return '/'.join((self.context.absolute_url(), '@@new_row'))

    @property
    def displaymode(self):
        if self.VIEWNAME == 'edit':
            return self.definition.multiform_entry_mode
        return self.definition.multiform_display_mode

    def field_info(self, field):
        is_col = ICollection.providedBy(field)
        vtype = field.value_type.__class__.__name__ if is_col else None
        return {
            'name': field.__name__,
            'title': field.title,
            'type': field.__class__.__name__,
            'value_type': vtype
            }

    def fields_json(self):
        schema = self.schema
        fields = map(lambda pair: pair[1], getFieldsInOrder(schema))
        return json.dumps({
            'fields': map(self.field_info, fields),
            })


class MultiFormDisplay(MultiFormEntry):
    VIEWNAME = 'view'


class MultiFormSave(MultiFormEntry):
    """Save only view (ajax): returns json of status messages"""

    def get_status_message(self):
        """get any set status message set during update()"""
        return [_utf8(msg.message) for msg in self._status.show()]

    def index(self, *args, **kwargs):
        messages = self.get_status_message()
        output = json.dumps({
            'messages': messages
            })
        self.request.response.setHeader('Content-Type', 'application/json')
        self.request.response.setHeader('Content-Length', len(output))
        return output

    def __call__(self, *args, **kwargs):
        kwargs['saveonly'] = True
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)


class MultiFormSaveSubmit(MultiFormSave):
    """Save and submit"""

    def update(self, *args, **kwargs):
        self.request.form['save_submit'] = True
        kwargs['saveonly'] = True
        super(MultiFormSaveSubmit, self).update(*args, **kwargs)

