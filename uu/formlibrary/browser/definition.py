from plone.z3cform.interfaces import IWrappedForm
from zope.interface import alsoProvides
from zope.schema import getFieldNamesInOrder

from uu.formlibrary.interfaces import IFormDefinition
from uu.formlibrary.forms import ComposedForm


class FormView(object):
    
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
        self._form.update()
        return self._form.render()
    
    def update(self, *args, **kwargs):
        self._form.update(*args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

