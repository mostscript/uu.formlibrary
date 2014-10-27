# views to output excel files

import tempfile

from plone.uuid.interfaces import IUUID

from uu.formlibrary.xls import FormWorkbook


class FormXLSView(object):
    """
    View for an individual form output to single-sheet MSExcel workbook.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def filename(self):
        return '%s-%s.xls' % (
            self.context.getId(),
            IUUID(self.context)[-12:],
            )

    def payload(self):
        stream = tempfile.TemporaryFile()
        workbook = FormWorkbook(stream)
        sheet = workbook.add(self.context)
        sheet.write()  # will call workbook.save()
        stream.seek(0)
        payload = stream.read()
        workbook.close()
        return payload

    def update(self, *args, **kwargs):
        pass

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

    def __call__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        return self.index(*args, **kwargs)

