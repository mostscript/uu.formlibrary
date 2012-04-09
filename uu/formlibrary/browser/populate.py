from itertools import product

from plone.autoform.form import AutoExtensibleForm
from plone.i18n.normalizer.interfaces import IURLNormalizer
from plone.z3cform.layout import FormWrapper
from z3c.form import button, form
from zope.component import queryUtility
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage

from uu.formlibrary.interfaces import IPopulateForms, IPeriodicSeries
from uu.formlibrary.interfaces import FORM_TYPE_NAMES
from uu.formlibrary import utils


strip = lambda v: v.strip()

def construct(context, type_name, id):
    context.invokeFactory(id=id, type_name=type_name)
    return context[id]


def series_range(context, formdata):
    """
    Returns series start, end, frequency label
    """
    # TODO: support range overrides from formdata (IPeriodicSeries) if 
    # override is specified.
    end = context.end or date(date.today().year,12,31) #default:EOY
    return context.start, end, context.frequency, context.active_weekdays


def title_variants(info, prefixes, suffixes):
    """For one range info object, return id, title variants/permutations"""
    result = []
    prefixes = filter(lambda v: bool(v), map(strip, prefixes))
    sufixes = filter(lambda v: bool(v), map(strip, suffixes))
    normalizer = queryUtility(IURLNormalizer)
    if prefixes and suffixes:
        for prefix, suffix in product(prefixes, suffixes):
            title = u'%s - %s - %s' % (prefix, info['title'], suffix)
            id = normalizer.normalize(title)
            result.append((id, title))
    elif not prefixes and not suffixes:
        title = info['title']
        result.append(normalizer.normalize(title), title)
    elif prefixes:
        for prefix in prefixes:
            title = u'%s - %s' % (prefix, info['title'])
            result.append(normalizer.normalize(title), title)
    elif suffixes:
        for suffix in suffixes:
            title = u'%s - %s' % (info['title'], suffix)
            result.append(normalizer.normalize(title), title)
    return result


class PopulateForms(AutoExtensibleForm, form.Form):
    """Populate forms wizard for form series"""
    
    ## settins for auto-form:
    ignoreContext = True
    autoGroups = True
    enable_form_tabbing = False  # display without form tabs
    
    schema = IPopulateForms
    additionalSchemata = (IPeriodicSeries,)

    def __init__(self, context, request):
        super(PopulateForms, self).__init__(context, request)
        ## don't use self.status from z3c.form, use plone status
        ## messages from Products.statusmessage
        self._status = IStatusMessage(self.request)
    
    def _nothing_to_do(self, reason=None):
        msg = u'Cannot populate forms: missing information'
        if reason is not None:
            msg += u' (%s)' % reason
        self._status.addStatusMessage(msg, type='info')
    
    def update(self, *args, **kwargs):
        super(PopulateForms, self).update()
        periodic_group = [g for g in self.groups
                            if g.label == u'IPeriodicSeries']
        if periodic_group:
            periodic_group[0].label = u'Custom frequency/duration range'
            periodic_group[0].description = u''

    @button.buttonAndHandler(u'Create forms using these rules')
    def handleApply(self, action):
        data, errors = self.extractData()
        if errors:
            self._status.addStatusMessage(
                u'There were errors populating forms.',
                type='error',
                )
            return
        created_count = 0
        typename = str(data['form_type'])
        typelabel = FORM_TYPE_NAMES.get(typename, unicode(typename))
        start, end, freq, weekdays = series_range(self.context, data)
        if start is None:
            return self._nothing_to_do(u'No start date specified.')
        if freq == 'Weekly':
            if not weekdays:
                return self._nothing_to_do(u'No active weekdays specified '\
                                           u'for a weekly period.')
            infocls = lambda d: utils.WeeklyInfo(d, days=weekdays)
        else:
            infocls = { 
                'Monthly'           : utils.MonthlyInfo,
                'Quarterly'         : utils.QuarterlyInfo,
                'Annual'            : utils.AnnualInfo,
                'Twice monthly'     : utils.TwiceMonthlyInfo,
                'Every two months'  : utils.EveryTwoMonthsInfo,
                'Every six months'  : utils.SemiAnnualInfo,
                }[freq]  
        infos = [dict(infocls(d)) for d in infocls(start).all_until(end)]
        for info in infos:
            ## every date slice
            variants = title_variants(
                info=info,
                prefixes=data['title_prefixes'],
                suffixes=data['title_suffixes'],
                )
            for id, title in variants:
                ## every title/id permutation for each date slice
                form = construct(self.context, typename, id)
                form.title = title
                form.start = info['start']
                form.end = info['end']
                form.definition = data.get('definition')
                form.description = u''
                form.reindexObject()
                created_count += 1
        self._status.addStatusMessage(
            u'%s form items created of type %s' % (
                created_count,
                typelabel,
                ),
            type='info',
            )


class PopulateFormsView(FormWrapper):
    """A wrapper view for PopulateForms"""
    
    form = PopulateForms 
    index = ViewPageTemplateFile('populate.pt')
     
    def __init__(self, context, request):
        FormWrapper.__init__(self, context, request)

