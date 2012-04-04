from plone.autoform import AutoExtensibleForm
from Products.statusmessages.interfaces import IStatusMessage

from uu.formlibrary.interfaces imrpot IPopulateForms, IPeriodicSeries


def construct(context, type_name, id):
    context.invokeFactory(id=id, type_name=type_name)
    return context[id]


def series_range(context, request):
    """
    Returns series start, end, frequency label
    """
    # TODO: support range overrides from request.
    end = context.end or date(date.today().year,12,31) #default:EOY
    return context.start, end, context.frequency


class PopulateForms(AutoExtensibleForm):
    """Populate forms wizard for form series"""
    
    ## settins for auto-form:
    ignoreContext = True
    autoGroups = True
    enable_form_tabbing = False  # display without form tabs
    
    schema = IPopulateForms
    additionalSchemata = IPeriodicSeries

    def __init__(self, context, request):
        super(PopulateForms, self).__init__(context, request)
        self.status = IStatusMessage(self.request)
    
    def _nothing_to_do(self, reason=None):
        msg = u'Cannot populate forms: missing information'
        if reason is not None:
            msg += u' (%s)' % reason
        self.status.addStatusMessage(msg, type='info')

    def update(self, *args, **kwargs):
        super(PopulateForms, self).update(*args, **kwargs)
        typename = str(self.request.form.get('form_type'))
        ## TODO : get info for each period
        start, end, freq, weekdays = series_range(self.context)
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
            pass # TODO : implement


        ## TODO : call factory adapter.

