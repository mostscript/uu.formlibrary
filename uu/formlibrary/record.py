from plone.uuid.interfaces import IUUID
from zope.interface import implements, implementer
from zope.component import adapter

from uu.formlibrary.interfaces import IFormEntry
from uu.dynamicschema.schema import SchemaSignedEntity


class FormEntry(SchemaSignedEntity):
    """
    Persistent record for form data:

    * Has a record_uid attribute containing and RFC 4122 UUID.

    * Is an entity signed bya schema and md5 signature of its serialization.

    * Is locatable named item providing zope.location.interfaces.ILocation

    * Provided persistence via SchemaSignedEntity base class, which is
      a subclass of uu.record.base.Record, which is persistent.
    """

    implements(IFormEntry)

    def __init__(self, context=None, uid=None):
        SchemaSignedEntity.__init__(self, context, uid)

    @property
    def schema(self):
        return SchemaSignedEntity.schema.__get__(self)


## IUUID adapter for FormEntry records
@implementer(IUUID)
@adapter(IFormEntry)
def record_uuid(context):
    return context.record_uid

