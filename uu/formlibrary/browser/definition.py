from collective.z3cform.datagridfield import DataGridField
from plone.z3cform.interfaces import IWrappedForm
from z3c.form.interfaces import IDataConverter
from zope.component import getMultiAdapter
from zope.interface import alsoProvides
from zope.schema import getFieldNamesInOrder

from uu.formlibrary.interfaces import IFormDefinition, ISimpleForm
from uu.formlibrary.forms import ComposedForm


class FormInputView(object):
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.definition = IFormDefinition(self.context) 
        self._form = ComposedForm(self.context, request)
        # non-intuitive, but the way to tell the renderer not to wrap
        # the form is to tell it that it is already wrapped.
        alsoProvides(self._form, IWrappedForm)
    
    def fieldnames(self):
        return getFieldNamesInOrder(self.definition.schema)

    def groups(self):
        return self._form.groups
   
    def render_form(self):
        for group in self._form.groups:
            fieldgroup = self._form.components.groups[group.__name__]
            if fieldgroup.group_usage != 'grid':
                group.updateWidgets()
        self._form.updateWidgets()
        if self._form.save_attempt:
            data, errors = self._form.extractData()
        return self._form.render()
   
    def _load_form_values_from_data(self):
        # call only after calling self._form.update()a
        if not ISimpleForm.providedBy(self.context):
            return # don't update definition or non-data context
        widget_prefix = 'form.widgets'
        form = self._form 
        data = self.context.data
        req = self.request
        groups = dict([(g.__name__, g) for g in form.groups])
        groupnames = [''] + groups.keys()
        for groupname in groupnames:
            group_data = data.get(groupname, None)  #for default group
            if groupname is '':
                group = form
            else:
                group = groups[groupname]
            if group_data is not None:
                for name, formfield in group.fields.items():
                    fullname = '.'.join((widget_prefix, name))
                    v_req = req.get(fullname, None)
                    if v_req is None:
                        # field not found in request, get from data
                        schema_name = name.replace('%s.' % groupname, '')
                        v_data = getattr(group_data, schema_name, None)
                        if v_data is not None:
                            spec = (formfield.field, group.widgets[name])
                            converter = getMultiAdapter(spec, IDataConverter)
                            if not form.save_attempt and isinstance(
                                    spec[1],
                                    DataGridField):
                                spec[1].value = v_data #sets, updates widgets
                            req.set(fullname, converter.toWidgetValue(v_data))
    
    def update(self, *args, **kwargs):
        self._form.update(*args, **kwargs)
        if self.definition is not self.context:
            self._load_form_values_from_data()
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)


class FormDisplayView(FormInputView):
    """ Display form: Form view in display mode without buttons """
    
    def __init__(self, context, request):
        super(FormDisplayView, self).__init__(context, request)
        self._form.mode = 'display'

