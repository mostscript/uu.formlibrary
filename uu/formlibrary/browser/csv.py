import tempfile
import zipfile

from zope.interface import implements
from AccessControl import getSecurityManager
from ZPublisher.Iterators import IStreamIterator

from uu.formlibrary.interfaces import IMultiFormCSV, IMultiForm, IFormSeries
from uu.formlibrary.measure.interfaces import IFormDataSetSpecification


class MultiFormCSVDownload(object):
    """view to download CSV for a multi-record form"""

    DISP = 'attachment; filename=%s'

    def __init__(self, context, request):
        if not IMultiForm.providedBy(context):
            raise ValueError('context must be multi-record form')
        self.context = context
        self.request = request

    def __call__(self, *args, **kwargs):
        filename = '%s.csv' % self.context.getId()
        csv = IMultiFormCSV(self.context)
        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Length', str(len(csv)))
        self.request.response.setHeader(
            'Content-Disposition',
            self.DISP % filename
            )
        return csv


class TempFileStreamIterator(object):
    """
    file stream iterator implementation for a temporary file; closes the
    file once iteration is complete to ensure tempfile is destroyed.
    This is an interface compatible replacement for filestream_iterator
    from ZPublisher, which requires a file path and does not issue a
    close operation on the file.
    """

    implements(IStreamIterator)

    def __init__(self, tmpfile, streamsize=(1 << 16)):
        if tmpfile.name != '<fdopen>':
            raise TypeError('%s is not unnamed temporary file' % tmpfile)
        self.tmpfile = tmpfile
        self.tmpfile.seek(0)
        self.streamsize = streamsize

    def next(self):
        data = self.tmpfile.read(self.streamsize)
        if not data:
            self.tmpfile.close()
            raise StopIteration
        return data

    def __len__(self):
        current = self.tmpfile.tell()
        self.tmpfile.seek(0, 2)  # EOF
        size = self.tmpfile.tell()
        self.tmpfile.seek(current)
        return size


class SeriesCSVArchiveView(object):
    """View for zip file output of a series including the CSV data"""

    DISP = 'attachment; filename=%s'

    def __init__(self, context, request):
        if not IFormSeries.providedBy(context):
            raise ValueError('%s does not provide IFormSeries' % context)
        self.context = context
        self.request = request

    def _forms(self):
        include = lambda o: IMultiForm.providedBy(o)
        return [o for o in self.context.objectValues() if include(o)]

    def __call__(self, *args, **kwargs):
        secmgr = getSecurityManager()
        forms = self._forms()
        output = tempfile.TemporaryFile(mode='w+b')
        archive = zipfile.ZipFile(output, mode='w')
        for form in forms:
            if not secmgr.checkPermission('View', form):
                continue  # omit/skip form to which user has no View permission.
            data = IMultiFormCSV(form)
            filename = '%s.csv' % form.getId()
            archive.writestr(filename, data)
        archive.close()
        output.seek(0)
        stream = TempFileStreamIterator(output)
        self.request.response.setHeader('Content-Type', 'application/zip')
        self.request.response.setHeader('Content-Length', len(stream))
        filename = '%s.zip' % self.context.getId()
        self.request.response.setHeader(
            'Content-Disposition',
            self.DISP % filename
            )
        return stream


class DatasetCSVArchiveView(SeriesCSVArchiveView):
    """View for a dataset for zip file of CSV output"""
    
    def __init__(self, context, request):
        if not IFormDataSetSpecification.providedBy(context):
            raise ValueError('Not data set')
        self.context = context
        self.request = request

    def _forms(self):
        include = lambda o: IMultiForm.providedBy(o)
        return [o for o in self.context.forms() if include(o)]

