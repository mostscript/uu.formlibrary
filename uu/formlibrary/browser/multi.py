import uuid

from plone.supermodel import serializeSchema
from zope.component import queryUtility
from z3c.form import form, field
from z3c.form.browser.radio import RadioFieldWidget
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.schema import getFieldsInOrder, getFieldNamesInOrder
from zope.schema.interfaces import IChoice, IList, IDate
from zope.app.component.hooks import getSite

from uu.dynamicschema.interfaces import ISchemaSaver
from uu.dynamicschema.schema import parse_schema
from uu.workflows.utils import history_log

from uu.formlibrary.interfaces import IFormSeries, IFormDefinition

from uu.smartdate.browser.widget import SmartdateFieldWidget

ROW_TEMPLATE = ViewPageTemplateFile('row.pt')
DIV_TEMPLATE = ViewPageTemplateFile('formdiv.pt')


class RowForm(form.EditForm):
    template = ROW_TEMPLATE
    def __init__(self, record, schema, request):
        self._rowform_rec = record
        self._rowform_schema = schema
        self.fields = field.Fields(schema)
        self.prefix = '%s~' % record.record_uid # (js should split on '~')
        super(RowForm, self).__init__(record, request)
    
    def updateWidgets(self):
        choicefields = [f.field for f in self.fields.values()
                            if IChoice.providedBy(f.field)]
        for field in choicefields:
            vocab = field.vocabulary
            if hasattr(vocab, '__len__') and hasattr(vocab, '__iter__'):
                #appears iterable, get number of choices
                if len(vocab) <= 3:
                    name = field.__name__
                    self.fields[name].widgetFactory = RadioFieldWidget
        multichoice = [f.field for f in self.fields.values()
                        if IList.providedBy(f.field) and
                            IChoice.providedBy(f.field.value_type)]
        for field in multichoice:
            vocab = field.value_type.vocabulary
            if hasattr(vocab, '__len__') and hasattr(vocab, '__iter__'):
                if len(vocab) <= 16:
                    name = field.__name__
                    self.fields[name].widgetFactory = CheckBoxFieldWidget
        datefields = [f.field for f in self.fields.values()
                        if IDate.providedBy(f.field)]
        for field in datefields:
            self.fields[field.__name__].widgetFactory = SmartdateFieldWidget
        super(RowForm, self).updateWidgets()


class DivRowForm(RowForm):
    template = DIV_TEMPLATE


class RowDisplayForm(form.DisplayForm):
    template = ROW_TEMPLATE
    def __init__(self, record, schema, request):
        self.fields = field.Fields(schema)
        super(RowDisplayForm, self).__init__(record, request)


class MultiFormEntry(object):

    VIEWNAME = 'edit'

    def __init__(self, context, request):
        self.series = context.__parent__
        self.context = context.__of__(self.series)
        self.definition = IFormDefinition(self.context)
        self.request = request
        self.seriesinfo = dict(
            [(k,v) for k,v in self.series.__dict__.items()
                if v is not None and k in getFieldNamesInOrder(IFormSeries)])
        self.title = '%s: %s' % (self.series.Title().strip(), context.Title())
        self._fields = []
        self._user_message = ''
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)  #index() via Five/framework magic
   
    def update(self, *args, **kwargs):
        if 'payload' in self.request.form:
            json = self.request.form.get('payload').strip()
            if json:
                oldkeys = self.context.keys()
                self.context.update_all(json)
                newkeys = self.context.keys()
                count_new = len(set(newkeys) - set(oldkeys))
                count_updated = len(set(oldkeys) & set(newkeys))
                count_removed = len(set(oldkeys) - set(newkeys))
                self._user_message = 'Data has been saved.'
                if count_new or count_updated or count_removed:
                    self._user_message += '('
                if count_new:
                    self._user_message += ' %s new entries. ' % count_new
                if count_updated:
                    self._user_message += ' %s updated entries. ' % (
                        count_updated,)
                if count_removed:
                    self._user_message += ' %s removed entries. ' % (
                        count_removed,)
                if count_new or count_updated or count_removed:
                    self._user_message += ')'
                history_log(self.context, self._user_message)
    
    @property
    def schema(self):
        entry_uids = self.context.keys()
        if not entry_uids:
            return self.definition.schema
        return self.context[entry_uids[0]].schema # of first contained record
    
    def user_message(self):
        return self._user_message
    
    def fields(self):
        if not self._fields:
            self._fields = getFieldsInOrder(self.schema)
        return [v for k,v in self._fields] #field objects
    
    def fieldnames(self):
        if not self._fields:
            self._fields = getFieldsInOrder(self.schema)
        return [k for k,v in self._fields] #field objects
    
    def logourl(self):
        filename = getattr(self.definition.logo, 'filename', None)
        if filename is None:
            return None
        base = self.definition.absolute_url()
        return '%s/@@download/logo/%s' % (base, filename)
    
    def portalurl(self):
        return getSite().absolute_url()
    
    def classname(self, name):
        """
        class name is two names separated by space: column number prefixed 
        by the letter 'c' and column name prefixed by 'col-'
        """
        if not isinstance(name, basestring):
            name = name.__name__ # assume field, not fieldname
        fieldnames = self.fieldnames()
        if name not in fieldnames:
            return 'c0 col-%s' % name
        return 'c%s col-%s' % (fieldnames.index(name), name)
   
    def entry_uids(self):
        if not hasattr(self.context, '_keys'):
            self._keys = self.context.keys() #ordered uids of entries
        return self._keys
    
    def rowform(self, uid=None):
        if uid is None or uid not in self.entry_uids():
            record = self.context.create() #create new with UUID
        else:
            record = self.context.get(uid)
        self._last_uid = record.record_uid
        if self.VIEWNAME == 'edit':
            if self.displaymode == 'Stacked':
                form = DivRowForm(record, record.schema, self.request)
            else:
                form = RowForm(record, record.schema, self.request)
        else:
            form = RowDisplayForm(record, record.schema, self.request)
        form.update()
        return form.render()
    
    def last_row_uid(self):
        """return the last row uid for row rendered by rowform or random"""
        if hasattr(self, '_last_uid'):
            return self._last_uid
        return str(uuid.uuid4()) #default random UUID is fallback only
    
    def new_row_url(self):
        return '/'.join((self.context.absolute_url(), '@@new_row'))
    
    @property
    def displaymode(self):
        return self.definition.multiform_display_mode


class MultiFormDisplay(MultiFormEntry):
    VIEWNAME = 'view'
 