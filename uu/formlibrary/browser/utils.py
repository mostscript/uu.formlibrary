from zope.interface import implements
from ZPublisher.Iterators import IStreamIterator


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
