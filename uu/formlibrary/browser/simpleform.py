from z3c.form import form, field
from zope.schema import getFieldNamesInOrder
from z3c.form.ptcompat import ViewPageTemplateFile


class EntryForm(form.EditForm):
    
    template = ViewPageTemplateFile('simple_entry_core.pt')
     
    def __init__(self, record, request, schema):
        self.context = record
        self.request = request
        self.fields = field.Fields(schema)
        super(EntryForm, self).__init__(record, request)
    
    def update(self, *args, **kwargs):
        if 'saveform' in self.request:
            pass #TODO



class SimpleFormEntry(object):
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.entry_form = EntryForm(
            self.context.data,
            request,
            self.context.schema,
            )
    
    def fieldnames(self):
        return getFieldNamesInOrder(self.context.schema)
   
    def render_form(self):
        self.entry_form.update()
        return self.entry_form.render()
    
    def update(self, *args, **kwargs):
        self.entry_form.update(*args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

