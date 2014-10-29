# views to output excel files

import tempfile

from Acquisition import aq_base
from plone.uuid.interfaces import IUUID

from uu.formlibrary.interfaces import IBaseForm, ISimpleForm, IMultiForm
from uu.formlibrary.xls import FormWorkbook


class BaseXLSView(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def filename(self):
        return '%s-%s.xls' % (
            self.context.getId(),
            IUUID(self.context)[-12:],
            )

    def update(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

    def index(self, *args, **kwargs):
        payload = self.payload()
        filename = self.filename()
        self.request.response.setHeader(
            'Content-Length',
            str(len(payload)),
            )
        self.request.response.setHeader(
            'Content-Type',
            'application/vnd.ms-excel',
            )
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="%s"' % filename,
            )
        return payload


class FormXLSView(BaseXLSView):
    """
    View for an individual form output to single-sheet MSExcel workbook.
    """

    def payload(self):
        stream = tempfile.TemporaryFile()
        workbook = FormWorkbook(stream)
        sheet = workbook.add(self.context)
        sheet.write()  # will call workbook.save()
        stream.seek(0)
        payload = stream.read()
        workbook.close()
        return payload


class SeriesXLSView(BaseXLSView):

    forms = ()

    def content(self):
        return self.context.objectValues()  # CMF/OFS contents
 
    def update(self, *args, **kwargs):
        self.forms = []
        for form in self.content():
            if not IBaseForm.providedBy(form):
                continue  # ignore non-form content
            if ISimpleForm.providedBy(form):
                self.forms.append(form)
            if IMultiForm.providedBy(form):
                continue  # ignore for now, implement eventually
        keyfn = lambda o: getattr(aq_base(o), 'start', None)
        self.forms = sorted(self.forms, key=keyfn)

    def payload(self):
        stream = tempfile.TemporaryFile()
        workbook = FormWorkbook(stream)
        for form in self.forms:
            sheet = workbook.add(form)
            sheet.write()  # will call workbook.save()
        stream.seek(0)
        payload = stream.read()
        workbook.close()
        return payload


class DatasetXLSView(SeriesXLSView):

    def content(self):
        return self.context.forms()  # IFormDataSetSpecification query res.

