import calendar
from datetime import date, datetime, timedelta
import re

from plone.autoform.interfaces import WIDGETS_KEY
from plone.schemaeditor import schema as se_schema
from collective.z3cform.datagridfield import DictRow
from zope.schema import List
from zope.schema.interfaces import ConstraintNotSatisfied

from uu.dynamicschema.schema import new_schema


# workaround for plone.schemaeditor / plone.formwidget.datetime conflict
def getDateFieldSchema(field):
    return se_schema.IDate


WIDGET = 'collective.z3cform.datagridfield.datagridfield.DataGridFieldFactory'

USA_DATE = re.compile('^([01]?[0-9])[/-]([0123]?[0-9])[/-]([0-9]+)$')


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
    grid.required = False  # ugly in form UI, widget will render regardless
    wrapper._InterfaceClass__attrs['data'] = grid
    # specify plone.autoform widget config for field:
    wrapper.setTaggedValue(WIDGETS_KEY, {'data': WIDGET})
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
        seq = list(seq)  # copy of original sequence we can pop nodes from
        if not seq:
            return True  # empty list: nothing to compare, nothing to get wrong
        if len(seq) > 7:
            raise exc('provided values exceed seven days')
        for name in seq:
            if name not in cls.WKDAYS:
                raise exc('provided value not day of week')
        seq_head = seq.pop(0)
        # align days of week, get node representing same day as head of seq.
        node = cls.chain()
        for i in range(0, 7):
            if seq_head == node.day:
                break
            node = node.next
        for i in range(0, 7):
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
        if k not in ('id', 'title', 'start', 'end'):
            raise KeyError(k)
        return getattr(self,
                       {'start': 'first_day',
                        'end': 'last_day',
                        'id': 'id',
                        'title': 'title'}[k])

    def _as_dict(self):
        keylist = ('id', 'title', 'start', 'end')
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

    def all_until(self, end, **kwargs):
        """
        return the first day of every period in the range
        """
        start = self.first_day
        result = []
        if start <= self.__class__(end).first_day:
            result = [start] + \
                self.__class__(self.next_period, **kwargs).all_until(end)
        return result


class DailyInfo(PeriodInfo):
    """For daily forms"""
    
    def __init__(self, context, days=DOW.WKDAYS, title_ending=True):
        if len(days) == 0:
            raise ValueError('list of provided days must not be empty')
        #invalid days seq: raise zope.schema.interfaces.ConstraintNotSatisfied
        if not all(map(lambda v: isinstance(v, int), days)):
            DOW.validate(days)
        super(DailyInfo, self).__init__(context)
        # save state of days as indexes matching date.weekday(), not names
        _day = lambda v: v if isinstance(v, int) else DOW.WKDAYS.index(v)
        self.days = [_day(v) for v in days]  # normalized to int indexes

    @property
    def first_day(self):
        d = self._as_date(self.context)
        while d.weekday() not in self.days:
            d = d + timedelta(days=1)
        return d

    @property
    def last_day(self):
        return self.first_day

    @property
    def next_period(self):
        d = self._as_date(self.context + timedelta(days=1))
        while d.weekday() not in self.days:
            d = d + timedelta(days=1)
        return d

    @property
    def title(self):
        cal = calendar.TextCalendar()
        d = self.first_day
        weekday = d.weekday()
        weekday = cal.formatweekday(weekday, 10).strip()
        month = cal.formatmonth(d.year, d.month).strip().split('\n')[0]
        month = month.split(' ')[0]  # name only
        return '%s, %s %s, %s' % (weekday, month, d.day, d.year)

    def all_until(self, end):
        return super(DailyInfo, self).all_until(end, days=self.days)


class QuarterlyInfo(PeriodInfo):

    def _qtr(self):
        return ((self.context.month - 1) / 3 + 1)

    @property
    def first_day(self):
        m = ((self._qtr() - 1) * 3 + 1)
        return self._as_date(self.context.replace(month=m, day=1))

    @property
    def next_period(self):
        thisq = self._qtr()
        nextq = thisq + 1 if thisq < 4 else 1
        year = self.context.year if thisq < 4 else self.context.year + 1
        m = ((nextq - 1) * 3 + 1)
        return self._as_date(self.context.replace(year=year, month=m, day=1))

    @property
    def title(self):
        qspelling = {
            1: 'first quarter',
            2: 'second quarter',
            3: 'third quarter',
            4: 'fourth quarter',
            }
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
        return self.CALFMT(d.year, d.month).strip().split('\n')[0]


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
        self.title_ending = title_ending  # title is end (not beginning)?

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
        return self._as_date(
            self.first_day + timedelta(days=len(self.days) - 1)
            )

    @property
    def title(self):
        if self.title_ending:
            return 'Week ending %s' % self.last_day.isoformat()
        return 'Week beginning %s' % self.first_day.isoformat()


class AnnualInfo(PeriodInfo):
    @property
    def first_day(self):
        return self.context.replace(month=1, day=1)

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
        self.title_ending = title_ending  # title is end (not beginning)?

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
        return self.context.replace(day=1)

    @property
    def next_period(self):
        d = self.context
        month = d.month + 2
        if month >= 13:
            return d.replace(year=d.year + 1, month=month % 13 + 1, day=1)
        return d.replace(month=month, day=1)

    @property
    def last_day(self):
        return self.next_period - timedelta(days=1)

    @property
    def title(self):
        d1 = self.first_day
        d2 = self.last_day
        m1 = self.CALFMT(d1.year, d1.month).strip().split(' ')[0]
        m2 = self.CALFMT(d2.year, d2.month).strip().split(' ')[0]
        return '%s (%s - %s)' % (d1.year, m1, m2)

    @property
    def id(self):
        v = self.title
        return v.replace(' ', '').replace('(', '-').replace(')', '').lower()


class EveryOtherMonthInfo(EveryTwoMonthsInfo):
    """
    Every other month means skip intervening months;
    start and end date should be in same month.
    """
    @property
    def last_day(self):
        month, year = self.context.month, self.context.year
        month = month + 1 if month < 12 else 1
        year = year + 1 if month == 1 else year
        next_month = self.context.replace(year=year, month=month, day=1)
        return next_month - timedelta(days=1)  # last day of this month

    @property
    def title(self):
        year, month = self.context.year, self.context.month
        return self.CALFMT(year, month).strip().split('\n')[0]


def local_query(context, query, types=None, depth=2):
    """
    Given a catalog search query dict and a context, restrict
    search to items contained in the context path or subfolders,
    and particularly only items of one or more content portal_type.

    Returns modified query dict for use with catalog search.
    """
    query = dict(query.items())  # cheap copy
    path = '/'.join(context.getPhysicalPath())
    query['path'] = {
        'query': path,
        'depth': depth,
        }
    if types is not None:
        query['portal_type'] = {
            'query': types,
            'operator': 'or',
            }
    return query


def normalize_usa_date(v):
    """
    normalize a date string value of m/d/y form to a datetime.date object.
    If normalization is not possible, return None.
    """
    if not isinstance(v, basestring):
        return None
    match = USA_DATE.search(v)
    if not match:
        return None
    groups = match.groups()
    try:
        month = int(groups[0])
        day = int(groups[1])
        year = int(groups[2])
    except TypeError:
        return None
    if not ((0 < month < 13) and (0 < day <= 31) and (0 < year)):
        return None
    if len(str(year)) <= 2:
        today = date.today()
        century_base = today.year - (today.year % 100)
        if year >= 70:
            century_base -= 100
        year = century_base + year
    if len(str(year)) != 4:
        return None
    try:
        if year < 1900:
            raise RuntimeError('dates prior to 1900 unsupported')  # for now
        return date(year, month, day)
    except ValueError:
        return None

