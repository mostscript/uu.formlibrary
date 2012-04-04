from plone.autoform.interfaces import WIDGETS_KEY
from collective.z3cform.datagridfield import DictRow, DataGridFieldFactory
from zope.schema import List
from zope.schema.interfaces import ConstraintNotSatisfied

from uu.dynamicschema.schema import new_schema


WIDGET = 'collective.z3cform.datagridfield.datagridfield.DataGridFieldFactory'

def grid_wrapper_schema(schema, title=u'', description=u''):
    """
    Given a schema interface for use in a data-grid, construct and 
    return a wrapper form interface to use that grid (DictRow).
    """
    # create empty new dynamic schema
    wrapper = new_schema()
    # inject a field into that schema interface
    grid = List(
        title=unicode(title),
        description=unicode(description),
        value_type=DictRow(schema=schema),
        )
    grid.__name__ = 'data'
    grid.interface = wrapper
    grid.required = False # ugly in form UI, widget will render regardless
    wrapper._InterfaceClass__attrs['data'] = grid
    # specify plone.autoform widget config for field:
    wrapper.setTaggedValue(WIDGETS_KEY, {'data' : WIDGET})
    return wrapper


class DOW(object):
    """
    Day of week circular linked list validation helper: used to create
    a chain or dial that has all days of week in repeating sequential
    for use in verification that any sequence of days between 0 and 7 days
    in a row is sequential, regardless of start date.
    """
    
    WKDAYS = ('Monday',
              'Tuesday',
              'Wednesday',
              'Thursday',
              'Friday',
              'Saturday',
              'Sunday')
    
    @classmethod
    def weekdays(cls):
        return list(cls.WKDAYS[0:5])
    
    def __init__(self, day, next=None):
        self.day = day
        self.next = next
    
    def __repr__(self):
        return '<%s object (day=%s, next=%s)>' % (self.__class__.__name__,
                                                  self.day,
                                                  self.next.day)
    
    @classmethod
    def chain(cls, days=None, head=None):
        if days is None:
            days = cls.WKDAYS
        chain = cls(days[0])
        if head is None:
            head = chain
        if len(days) > 1:
            chain.next = cls.chain(days[1:], head)
        else:
            chain.next = head
        return chain
    
    @classmethod
    def validate(cls, seq, exc=ConstraintNotSatisfied):
        """
        Returns False if order is incorrect; true if order is correct; 
        raises Exception using exc class argument if any value passed in 
        seq does not appear to be a weekday.  Number of days in sequence
        should not exceed a single week (seven).
        """
        seq = list(seq) #copy of original sequence we can pop nodes from
        if not seq:
            return True #empty list: nothing to compare, nothing to get wrong!
        if len(seq) > 7:
            raise exc('provided values exceed seven days')
        for name in seq:
            if name not in cls.WKDAYS:
                raise exc('provided value not day of week')
        seq_head = seq.pop(0)
        # align days of week, get node representing same day as head of seq.
        node = cls.chain()
        for i in range(0,7):
            if seq_head == node.day:
                break
            node = node.next
        for i in range(0,7):
            node = node.next
            try:
                v = seq.pop(0)
            except IndexError:
                break
            if v != node.day:
                raise exc('provided values are not in sequential order')
        return True

