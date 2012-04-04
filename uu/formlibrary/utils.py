import calendar
from datetime import date, datetime, timedelta

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


# weekly:
week_title = lambda d: "Week ending %s" % d.isoformat()


class PeriodInfo(object):
    """Abstract base period info class"""
    def __init__(self, context):
        if not (isinstance(context, datetime) or isinstance(context, date)):
            raise ValueError('context for period must be date or datetime')
        self.context = context
    
    def _as_date(self, value):
        return value if isinstance(value, date) else value.date()
    
    @property
    def first_day(self):
        raise NotImplementedError('Abstract')
    
    @property
    def next_period(self):
        raise NotImplementedError('Abstract')
    
    @property
    def last_day(self):
        return self._as_date(self.next_period - timedelta(days=1))
    
    @property
    def title(self):
        return "Period beginning %s" % self.context.isoformat()
    
    @property
    def id(self):
        return self.first_day.isoformat()
    
    def __getitem__(self, k):
        if k not in ('id','title','start','end'):
            raise KeyError(k)
        return getattr(self,
                       {'start' :'first_day',
                        'end'   :'last_day',
                        'id'    :'id',
                        'title' :'title'}[k])
    
    def _as_dict(self):
        keylist = ('id','title','start','end')
        return dict([(k, self[k]) for k in keylist])
    
    def next(self):
        k = self._d.next()
        return (k, self[k])
    
    def __iter__(self):
        """Used in concert with __getitem__ cast object to dict"""
        self._d = iter(self._as_dict())
        return self
    
    def __str__(self):
        return self.title
    
    def all_until(self, end):
        """
        return the first day of every period in the range
        """
        start = self.first_day
        result = []
        if start <= self.__class__(end).first_day:
            result = [start] + \
                     self.__class__(self.next_period).all_until(end)
        return result


class QuarterlyInfo(PeriodInfo):
    
    def _qtr(self):
        return ((self.context.month - 1)/3 + 1)
    
    @property
    def first_day(self):
        m = ((self._qtr() - 1) * 3 + 1)
        return self._as_date(self.context.replace(month=m, day=1))
    
    @property
    def next_period(self):
        thisq = self._qtr()
        nextq = thisq+1 if thisq < 4 else 1
        year = self.context.year if thisq < 4 else self.context.year+1
        m = ((nextq-1)*3 + 1)
        return self._as_date(self.context.replace(year=year, month=m, day=1))
    
    @property
    def title(self):
        qspelling = { 1: 'first quarter',
                      2: 'second quarter',
                      3: 'third quarter',
                      4: 'fourth quarter', }
        return '%s %s' % (self.context.year, qspelling[self._qtr()])


class MonthlyInfo(PeriodInfo):
    
    CALFMT = calendar.TextCalendar().formatmonth
    
    @property
    def first_day(self):
        return self.context.replace(day=1)
    
    @property
    def next_period(self):
        dt = self.context
        return self._as_date(dt.replace(
            year=(dt.year + (dt.month / 12)),
            month=(dt.month % 12) + 1,
            day=1,
            ))
    
    @property
    def title(self):
        d = self.context
        return self.CALFMT(d.year,d.month).strip().split('\n')[0]


class WeeklyInfo(PeriodInfo):
    """
    Week info given a white-list of sequential days to include in period.
    Monday is considered the first day of the week by default, and Sunday
    is considered the last.  This can be overwritten on construction passing
    a list of day names (a slice of interfaces.DOW.WKDAYS).
    """
    
    def __init__(self, context, days=DOW.WKDAYS, title_ending=True):
        if len(days) == 0:
            raise ValueError('list of provided days must not be empty')
        #invalid days seq: raise zope.schema.interfaces.ConstraintNotSatisfied 
        DOW.validate(days)
        super(WeeklyInfo, self).__init__(context)
        # save state of days as indexes matching date.weekday(), not names
        self.days = [DOW.WKDAYS.index(dayname) for dayname in days]
        self.title_ending = title_ending #title is end (not beginning)?
    
    @property
    def first_day(self):
        today_dow = self.context.weekday()
        first_dow = self.days[0]
        if today_dow < first_dow:
            offset = today_dow - (first_dow - 7)
        else:
            offset = today_dow - first_dow
        return self.context - timedelta(days=offset)
    
    @property
    def next_period(self):
        return self.first_day + timedelta(days=7)
    
    @property
    def last_day(self):
        return self._as_date(self.first_day + timedelta(days=len(self.days)-1))
    
    @property
    def title(self):
        if self.title_ending:
            return 'Week ending %s' % self.last_day.isoformat()
        return 'Week beginning %s' % self.first_day.isoformat()


class AnnualInfo(PeriodInfo):
    @property
    def first_day(self):
        return self.context.replace(month=1,day=1)
    
    @property
    def last_day(self):
        return self.context.replace(month=12, day=31)
    
    @property
    def next_period(self):
        return self.first_day.replace(year=self.context.year + 1)
    
    @property
    def id(self):
        return self.title.replace(' ', '-')
    
    @property
    def title(self):
        return '%s annual' % self.context.year


class TwiceMonthlyInfo(PeriodInfo):

    def __init__(self, context, title_ending=True):
        super(TwiceMonthlyInfo, self).__init__(context)
        self.title_ending = title_ending #title is end (not beginning)?
    
    @property
    def first_day(self):
        if self.context.day > 15:
            return self.context.replace(day=16)
        return self.context.replace(day=1)
    
    @property
    def last_day(self):
        if self.context.day > 15:
            return MonthlyInfo(self.context).last_day
        return self.context.replace(day=15)
    
    @property
    def next_period(self):
        return self.last_day + timedelta(days=1)
    
    @property
    def title(self):
        if self.title_ending:
            return 'Period ending %s' % self.last_day.isoformat()
        return super(TwiceMonthlyInfo, self).title
    
    @property
    def id(self):
        return self.title.replace(' ', '-').lower()


class SemiAnnualInfo(PeriodInfo):
    """Twice annually"""
    
    @property
    def first_day(self):
        if self.context.month > 6:
            return self.context.replace(month=7, day=1)
        return self.context.replace(month=1, day=1)
    
    @property
    def last_day(self):
        if self.context.month > 6:
            return self.context.replace(month=12, day=31)
        return self.context.replace(month=6, day=30)
    
    @property
    def next_period(self):
        return self.last_day + timedelta(days=1)
    
    @property
    def title(self):
        if self.context.month > 6:
            return '%s (2nd half)' % self.context.year
        return '%s (1st half)' % self.context.year
    
    @property
    def id(self):
        if self.context.month > 6:
            return '2H%s' % self.context.year
        return '1H%s' % self.context.year


class EveryTwoMonthsInfo(PeriodInfo):
    """Every two months"""
    
    CALFMT = calendar.TextCalendar().formatmonth
    
    @property
    def first_day(self):
        """replace with the first of the odd month for the period we are in"""
        month = self.context.month + self.context.month % 2 - 1
        return self.context.replace(month=month, day=1)
    
    @property
    def next_period(self):
        d = self.context
        month = d.month + d.month % 2 + 1
        if month == 13:
            return d.replace(year=d.year+1, month=1, day=1)
        return d.replace(month=month, day=1)
    
    @property
    def last_day(self):
        return self.next_period - timedelta(days=1)
    
    @property
    def title(self):
        d1 = self.first_day
        d2 = self.last_day
        m1 = self.CALFMT(d1.year,d1.month).strip().split(' ')[0]
        m2 = self.CALFMT(d2.year,d2.month).strip().split(' ')[0]
        return '%s (%s - %s)' % (d1.year, m1, m2)
    
    @property
    def id(self):
        v = self.title
        return v.replace(' ','').replace('(','-').replace(')','').lower()

