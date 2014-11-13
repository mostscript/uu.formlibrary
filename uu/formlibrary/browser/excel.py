# views to output excel files

import tempfile

from AccessControl import getSecurityManager
from Acquisition import aq_base
from plone.uuid.interfaces import IUUID
from zope.schema import getFieldNamesInOrder

from uu.formlibrary.interfaces import IBaseForm, ISimpleForm, IMultiForm
from uu.formlibrary.interfaces import IFormDefinition, IFormComponents
from uu.formlibrary.xls import FormWorkbook

from utils import TempFileStreamIterator

_marker = object()


def fieldset_nonempty(record, schema):
    # we have to go through a funny dance to avoid default values from
    # SchemaSignedEntity.__getattr__ on the record:
    uid = record.record_uid  # noqa -- just here to unghost, if needed
    _hasattr = lambda o, name: o.__dict__.get(name, _marker) is not _marker
    return any(_hasattr(record, name) for name in getFieldNamesInOrder(schema))


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

    def payload(self):
        """should return string or TempFileStreamIterator object"""
        raise NotImplementedError('base method is abstract')

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
        output = tempfile.TemporaryFile()
        workbook = FormWorkbook(output)
        sheet = workbook.add(self.context)
        sheet.write()  # will call workbook.save()
        output.seek(0)
        return TempFileStreamIterator(output)


class SeriesXLSView(BaseXLSView):

    forms = ()

    def content(self):
        return self.context.objectValues()  # CMF/OFS contents

    def _flex_form_hasdata(self, form):
        definition = IFormDefinition(form)
        groups = IFormComponents(definition).groups
        # form.data will not contain fieldset records on created but
        # otherwise unsaved form:
        _fieldsets = dict([(k, form.data.get(k)) for k in groups.keys()])
        # scenario 1: form exists, but no fieldset records (never entered):
        if not all(_fieldsets.values()):
            return False
        # scenario 2: form exists, but fieldset records may or may not be
        #             empty; if empty, return False -- otherwise True.
        return any(
            fieldset_nonempty(r, groups.get(k).schema)
            for k, r in _fieldsets.items()
            if getFieldNamesInOrder(groups.get(k).schema)
            )

    def update(self, *args, **kwargs):
        secmgr = getSecurityManager()
        self.forms = []
        for form in self.content():
            if not secmgr.checkPermission('View', form):
                continue  # user does not have permission to include form
            if not IBaseForm.providedBy(form):
                continue  # ignore non-form content
            if ISimpleForm.providedBy(form):
                if self._flex_form_hasdata(form):
                    self.forms.append(form)
            if IMultiForm.providedBy(form):
                notes = getattr(form, 'entry_notes', '') or ''
                if len(form.keys()) or notes:
                    self.forms.append(form)  # non-empty multiform
        keyfn = lambda o: getattr(aq_base(o), 'start', None)
        self.forms = sorted(self.forms, key=keyfn)

    def payload(self):
        output = tempfile.TemporaryFile()
        workbook = FormWorkbook(output)
        for form in self.forms:
            sheet = workbook.add(form)
            sheet.write()  # will call workbook.save()
        output.seek(0)
        return TempFileStreamIterator(output)


class DatasetXLSView(SeriesXLSView):

    def content(self):
        return self.context.forms()  # IFormDataSetSpecification query res.
