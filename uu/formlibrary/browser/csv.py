import tempfile
from StringIO import StringIO
import urllib
import zipfile

from zope.component.hooks import getSite
from zope.interface import implements
from AccessControl import getSecurityManager
from ZPublisher.Iterators import IStreamIterator

from uu.formlibrary.interfaces import IMultiFormCSV, IMultiForm, IFormSeries
from uu.formlibrary.measure.interfaces import IFormDataSetSpecification


def relpath(context):
    rootpath = getSite().getPhysicalPath()
    path = context.getPhysicalPath()
    return '/'.join(path[len(rootpath):])


def csv_meta_header(context):
    out = StringIO()
    title = urllib.quote(
        '%s -- %s' % (
            context.__parent__.Title(),
            context.Title()
            )
        )
    print >> out, "Form data export from: '%s'" % title
    print >> out, "Located at: %s" % urllib.quote(relpath(context))
    print >> out, "From site: %s" % getSite().absolute_url()
    print >> out, '-----'
    out.seek(0)
    return out.read()


class MultiFormCSVDownload(object):
    """view to download CSV for a multi-record form"""

    DISP = 'attachment; filename=%s'

    def __init__(self, context, request):
        if not IMultiForm.providedBy(context):
            raise ValueError('context must be multi-record form')
        self.context = context
        self.request = request

    def content(self):
        bom = u'\ufeff'.encode('utf8')  # UTF-8 BOM for MSExcel
        meta = csv_meta_header(self.context)
        csv = IMultiFormCSV(self.context)
        return '\n'.join((bom, meta, csv))

    def __call__(self, *args, **kwargs):
        filename = '%s.csv' % self.context.getId()
        output = self.content()
        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Length', str(len(output)))
        self.request.response.setHeader(
            'Content-Disposition',
            self.DISP % filename
            )
        return output


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
            data = MultiFormCSVDownload(form, self.request).content()
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

