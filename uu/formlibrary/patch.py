import sys

from zExceptions import Unauthorized
from ZPublisher.HTTPResponse import HTTPResponse

UA_NO_REDIRECTS = ('Excel/', 'Word/', 'ms-office')

#orig_setResponse = HTTPResponse.setResponse
orig_exception = HTTPResponse.exception


def exception(self, fatal=0, info=None, *args, **kwargs):
    """
    Monkey patch (wrapper) for HTTPResponse.exception, avoids 302
    authentication redirect for MS Office clients (only for forms),
    otherwise delegates to original implementation.

    Works around obnoxious treatment of hyperlinks on MSOffice (Mac, Win)
    and its presumptive use of Microsoft Office Protocol Discovery to
    poke at the URL prior to opening in a browser.

    Requires traversal machinery (e.g. browserDefault() method of form
    view) copy the request user-agent string to the response's
    '_req_user_agent' attribute.
    """
    
    if isinstance(info, tuple) and len(info) == 3:
        t, v, tb = info
    else:
        t, v, tb = sys.exc_info()
    if issubclass(t, Unauthorized):
        ua = getattr(self, '_req_user_agent', '')
        match = lambda v: v in ua
        if ua and any(map(match, UA_NO_REDIRECTS)):
            body = '<html><body>Hello</body></html>'
            self.setStatus(200)
            self.setBody(body)
            return body
    return orig_exception(self, fatal, info, *args, **kwargs)


HTTPResponse.exception = exception
