# uu.formlibrary package
import sys
import logging

from zope.i18nmessageid import MessageFactory


PKGNAME = 'uu.formlibrary'


_ = MessageFactory(PKGNAME)


product_log = logging.getLogger(PKGNAME)
product_log.addHandler(logging.StreamHandler(sys.stderr))

