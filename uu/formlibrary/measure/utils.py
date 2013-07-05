import hashlib
import hmac
import base64
import pickle

from plone.app.layout.navigation.root import getNavigationRoot


class SignedDataStreamCodec(object):
    """
    Return Base64 encoded payload of HMAC-SHA256 signed message.  The first
    64 bytes of the (unencoded, prior to Base64) data stream is the HMAC
    signature, and the rest of the message is the original data.
    """

    def __init__(self, key):
        self.secret = key

    def signature(self, msg):
        return hmac.new(
            self.secret,
            msg,
            digestmod=hashlib.sha256,
            ).hexdigest()

    def authenticate(self, signature, msg):
        """
        Authenticate msg against signature using secret key, returns bool.
        """
        return signature == self.signature(msg)

    def encode(self, msg):
        msg = str(msg)
        return base64.b64encode(self.signature(msg) + msg)

    def decode(self, stream):
        """Decode stream, authenticate, will return None on inauthentic"""
        input = base64.b64decode(stream)
        signature, msg = input[:64], input[64:]
        if not self.authenticate(signature, msg):
            return None
        return msg


class SignedPickleIO(object):
    """
    Encoder / decoder for HMAC-SHA256 signed, Base64 encoded pickle
    serialization (where the message is concatenated to the HMAC signature
    prior to Base64 encoding.  Signing and authentication use a secret
    key passed on construction of this component.
    """

    def __init__(self, key):
        self.secret = key

    def dumps(self, obj, protocol=0):
        raw = pickle.dumps(obj, protocol)
        codec = SignedDataStreamCodec(self.secret)
        return codec.encode(raw)  # base64 encoded signature plus pickle

    def loads(self, stream):
        """Load stream or return None if stream cannot be authenticated"""
        data = SignedDataStreamCodec(self.secret).decode(stream)
        if data is None:
            return None
        return pickle.loads(data)


def content_path(item):
    """
    Path to the content item relative to the navigation root of the
    context.
    """
    navroot_path = getNavigationRoot(item).split('/')
    exclude_count = len(navroot_path)
    return '/'.join(item.getPhysicalPath()[exclude_count:])  # rel. to root

