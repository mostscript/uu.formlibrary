/**
 * formskip.js: field rules / skip patterns basic implementation.
 * (c) 2015 The University of Utah / MIT licensed.
 *
 * Jargon
 * ------
 *
 *  - Condition ('when'): evalute a form (record) for such condition, and
 *                        when evaluted to true, action should take place.
 *
 *  - Action ('act'): something to be done to one field, applying an effect.
 *
 *  - Trigger field:  a field that by itself or with other fields is
 *                    considered to evaluate a rule.
 *
 *  - Contingent field: a field affected by a rule's action.
 *
 * JSON used for declaring skip pattern field rules
 * ------------------------------------------------
 *
 *  Top-level object contains optional 'rules' attribute, which is an Array
 *  that may be empty; should JSON be empty object, or rules be empty or
 *  null, rules are not considered for forms.
 *
 *  Each element of the 'rules' Array is an object with two properties:
 *  'when' (object) and 'act' (Array).  The 'when' object contains two
 *  possible properties, 'operator' and 'query'.  'operator' has only two
 *  legal values of 'or' or 'and'; 'query' is an Array of objects each
 *  comprising a "field query" of one field, having attributes of 'field'
 *  (string name), 'comparator' (see below), 'value' (field value, which
 *  may or may not be normalized).
 *
 *  Supported comparators: 'Eq', 'NotEq'
 *
 */

/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */


var formskip = (function ($) {

  var ns = {};

  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };

  // mapping of rules: keys are uuids assigned at load time, values rule obj.
  ns.rules = {};

  // array to keep order/sequence, stores uuids of rules:
  ns.ruleIds = [];

  // mapping of trigger field names to rules;
  //    keys are fieldnames, values are Array of (generated)
  //    uuids for each rule applicable to fieldname.
  ns.rulemap = {};

  // namespace for actions:
  ns.actions = {};

  // namespace for comparator functions:
  ns.compare = {
    Eq: function (a, b) { return a == b; },
    NotEq: function (a, b) { return a != b; }
  };

  ns.formData = function (form) {
    /* Get data for form, defer to native form implementation */
    return uu.formlibrary.multiform.getform(form.attr('id'));
  };

  ns.loadRule = function (rule) {
    var uid = ns.uuid4();
    if (!rule || !rule.when || !(rule.when.query instanceof Array)) return;
    ns.rules[uid] = rule;
    ns.ruleIds.push(uid);  // to preserve order
    rule.when.query.forEach(function (q) {
        var fieldname = q.field;
        if (!fieldname) return;
        if (Object.keys(ns.rulemap).indexOf(fieldname) === -1) {
          ns.rulemap[fieldname] = [];
        }
        ns.rulemap[fieldname].push(uid);
      }
    );
  };

  ns.loadRules = function (data) {
    data = data || {};
    (data.rules || []).forEach(ns.loadRule);
  };

  ns.fieldDiv = function (form, fieldname) {
    var prefix = $(form).attr('id'),
        sep = '\\~-',  // escape tilde (legal html5 char) to make jQuery happy
        fieldSpec = '#' + prefix + '\\~-' + fieldname;
    return $(fieldSpec, form);
  };

  ns.fieldValue = function (form, fieldname) {
    var fieldDiv = ns.fieldDiv(form, fieldname),
        formData = ns.formData(form);
    return formData[fieldname];
  };

  ns.queryMet = function (query, opts) {
    /* is single-field query met by form? */
    var form = $(opts.form),
        fieldname = query.field,
        sameField = opts.field === query.field && opts.field !== '@form',
        value = (sameField) ? opts.value : ns.fieldValue(form, fieldname),
        compare = ns.compare[query.comparator] || ns.compare.Eq;
    return compare(query.value, value);
  };

  ns.doAction = function (form, action, opts) {
    /** primary broker to delegate action for form */
    var name = action.action,
        field = action.field,
        knownAction = (Object.keys(ns.actions).indexOf(name) !== -1),
        callable = (knownAction) ? ns.actions[name] : function () {};
    callable(form, action, opts);
  };

  ns.doActions = function (rule, opts, key) {
    key = (key === 'otherwise') ? key : 'act';
    (rule[key] || []).forEach(function (action) {
      ns.doAction(opts.form, action, opts);
    });
  };

  ns.actOnRule = function (rule, opts) {
    ns.doActions(rule, opts, 'act');
  };

  ns.actOtherwise = function (rule, opts) {
    ns.doActions(rule, opts, 'otherwise');
  };

  ns.considerRule = function (rule, opts) {
    var queries = ((rule.when || {}).query || []),
        met = function (query) { return ns.queryMet(query, opts); },
        any = function (s) {
          return s.reduce(function (a, b) {
            return a || b;
          });
        },
        all = function (s) {
          return s.reduce(function (a, b) {
            return a == b && a;
          });
        },
        condFn = (rule.when.operator === 'or') ? any : all,
        conditionMet = false;
    // no queries, return:
    if (!queries.length) return;
    // are any (or) / all (and) queries met?
    conditionMet = condFn(queries.map(met));
    if (!conditionMet) {
      if (rule.otherwise && rule.otherwise.length) {
        ns.actOtherwise(rule, opts);
      }
      return;
    }
    ns.actOnRule(rule, opts);
  };

  ns.triggerFieldChanged = function (opts) {
    var ruleUIDs = ns.rulemap[opts.field] || [],
        rules = ruleUIDs.map(function (uid) { return ns.rules[uid]; });
    rules.forEach(function (rule) {
      ns.considerRule(rule, opts);
    });
  };

  ns.fieldImplicated = function (fieldname) {
    return Object.keys(ns.rulemap).indexOf(fieldname) !== -1;
  };

  ns.onFieldChange = function (opts) {
    var fieldname = opts.field,
        implicatedTrigger = ns.fieldImplicated(fieldname);
    if (!implicatedTrigger) return;
    ns.triggerFieldChanged(opts);
  };

  ns.onFormAdded = function (opts) {
    // evaluate rules in order on each new form record:
    ns.ruleIds.forEach(function (uid) {
      var rule = ns.rules[uid];
      ns.considerRule(rule, opts);
    });
  };

  ns.initListener = function () {
    var _fieldname = function (field) { return field.name; },
        fields = JSON.parse($('#field-json').text()).fields.map(_fieldname);
    fields.forEach(function (fieldname) {
      formevents.subscribe({
        field: fieldname,
        event: 'change',
        callback: ns.onFieldChange
      });
    });
    formevents.subscribe({
      field: '@form',
      event: 'added',
      callback: ns.onFormAdded
    });
  };

  ns.load = function () {
    var viewname = $('#formcore').attr('data-viewname'),
        basePath = window.location.pathname.split('@@')[0],
        rnd = (Math.floor(Math.random() * Math.pow(10,8))),
        rulesURL = basePath + '@@field_rules?cache_bust=' + rnd;
    if (viewname !== 'edit') return;  // only on form entry
    $.ajax({
      url: rulesURL,
      success: ns.loadRules
    });
    ns.initListener();
  };
 
  document.addEventListener('DOMContentLoaded', function () {
    ns.load();
  });

  // action defninitions, each taking three arguments:
  //    1. form context
  //    2. action object, which possibly includes configuration used by action
  //    3. opts: event options passed from event notification (trigger)

  ns.actions.disable = function (form, action, opts) {
    var container = ns.fieldDiv(form, action.field),
        input = $("input, textarea, select", container),
        isSelect = (input.length && input[0].tagName !== 'select'),
        roAttr = (isSelect) ? 'disabled' : 'readonly'; 
    if (!container.length) return;  // nothing to do, no field div to get
    // make input readonly (input, textarea), or disabled (select)
    if (input.length) {
      input.attr(roAttr, 'true');
    }
    container.addClass('disabled');
  };

  ns.actions.enable = function (form, action, opts) {
    var container = ns.fieldDiv(form, action.field),
        input = $("input, textarea, select", container),
        isSelect = (input.length && input[0].tagName !== 'select'),
        roAttr = (isSelect) ? 'disabled' : 'readonly'; 
    if (!container.length) return;  // nothing to do, no field div to get
    // Stop using readonly/disabled, if set:
    if (input.length) {
      input.removeAttr(roAttr);
    }
    container.removeClass('disabled');
  };
  return ns;

}(jQuery));
