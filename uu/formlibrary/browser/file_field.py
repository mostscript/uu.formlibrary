from plone.app.blob.iterators import BlobStreamIterator
from plone.namedfile.interfaces import INamedFileField
from zope.schema import getFieldsInOrder

from uu.formlibrary.interfaces import IFormDefinition


class FormFileDownloadView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _file_field_name(self):
        schema = IFormDefinition(self.context).schema
        for (name, field) in getFieldsInOrder(schema):
            if INamedFileField.providedBy(field):
                return name

    def _file_data(self):
        fieldname = self._file_field_name()
        if fieldname is None:
            return None
        record = self.context.data['']
        return getattr(record, fieldname, None)

    def __call__(self, *args, **kwargs):
        resp = self.request.response
        data = self._file_data()
        if data is None:
            raise RuntimeError('No file data contained in form')
        resp.setHeader('Content-Type', data.contentType)
        resp.setHeader(
            'Content-Disposition',
            'attachment; filename="%s"' % data.filename.encode('utf-8')
            )
        resp.setHeader('Content-Length', data.getSize())
        return BlobStreamIterator(data)

