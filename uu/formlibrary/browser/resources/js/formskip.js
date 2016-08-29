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
 *  Supported comparators:
 *    'Eq'
 *    'NotEq'
 *    'Contains' (substring in text)
 *    'Any'
 *    'All'
 *    'Gt'
 *    'Lt'
 *    'Ge'
 *    'Le'
 *
 */

/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */


var formskip = (function ($) {

  var ns = {};

  // utility functions:
  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };

  ns.any = function (s) {
    return s.reduce(function (a, b) {
      return a || b;
    });
  };

  ns.all = function (s) {
    return s.reduce(function (a, b) {
      return a == b && a;
    });
  };

  ns.asArray = function (v) {
    return (!(v instanceof Array) && typeof v !== 'object') ? [v] : v;
  };

  ns.asNumber = function (v) {
    var toInt = function (v) { return parseInt(v, 10); },
        normalize = (v.indexOf('.') !== -1) ? parseFloat : toInt;
    return normalize(v);
  };

  ns.normalizedActual = function (query, actual) {
    if (typeof query === 'number' && typeof actual === 'string') {
      actual = ns.asNumber(actual);
    }
    return actual;
  };

  ns.escapeId = function (id) {
    if (id && /^\d$/.test(id[0])) {
      id = '\\3' + id[0] + ' ' + id.slice(1);  // escape leading digit/hexdigit
    }
    id = id.replace('~', '\\~');               // escape tilde, if applicable
    return id;
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
    // compare query, actual
    Eq: function (a, b) { return a == b; },
    NotEq: function (a, b) { return a != b; },
    Any: function (query, actual) {
      query = ns.asArray(query);
      actual = ns.asArray(actual);
      return ns.any(
        query.map(function (v) { return actual.indexOf(v) !== -1; })
      );
    },
    All: function (query, actual) {
      query = ns.asArray(query);
      actual = ns.asArray(actual);
      return ns.all(
        query.map(function (v) { return actual.indexOf(v) !== -1; })
      );
    },
    Contains: function (query, actual) {
      /** Substring search;
        *   if query is multiple terms, 'or' them implicitly */
      query = ns.asArray(query);
      return ns.any(
        query.map(function (term) {
          // ensure lower case:
          term = (typeof term === 'string') ? term.toLowerCase() : null;
          // do not oblige empty-string false-positive:
          term = term || null;
          // case-insenstive substring match?
          return actual.toLowerCase().indexOf(term) !== -1;
        })
      );
    },
    Gt: function (query, actual) {
      return ns.normalizedActual(query, actual) > query;
    },
    Lt: function (query, actual) {
      return ns.normalizedActual(query, actual) < query;
    },
    Ge: function (query, actual) {
      return ns.normalizedActual(query, actual) >= query;
    },
    Le: function (query, actual) {
      return ns.normalizedActual(query, actual) <= query;
    },
    NotAll: function (query, actual) {
      return !ns.compare.All(query, actual);
    },
    NotAny: function (query, actual) {
      return !ns.compare.Any(query, actual);
    }
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
    var prefix = ns.escapeId($(form).attr('id')),
        sep = '\\~-',  // escape tilde (legal html5 char) to make jQuery happy
        fieldSpec = '#' + prefix + '\\~-' + fieldname;
    return $(fieldSpec, form);
  };

  ns.fieldValue = function (form, fieldname) {
    /* delegate to implementation to get a field value given form, fieldname */
    return uu.formlibrary.multiform.getValue(form, fieldname);
  };

  ns.getComparator = function (name) {
    name = name[0].toUpperCase() + name.slice(1);
    return ns.compare[name] || ns.compare.Eq;
  };

  ns.normalizeBoolean = function (v) {
    if (v instanceof Array && v.length) v = v[0];
    if (v === 'true') return true;
    if (v === 'false') return false;
    return v;
  };

  ns.queryMet = function (query, opts) {
    /* is single-field query met by form? */
    var form = $(opts.form),
        queryValue = query.value,
        fieldname = query.field,
        sameField = opts.field === query.field && opts.field !== '@form',
        value = (sameField) ? opts.value : ns.fieldValue(form, fieldname),
        compare = ns.getComparator(query.comparator);
    if (typeof value === 'boolean' || typeof queryValue === 'boolean') {
      queryValue = ns.normalizeBoolean(queryValue);
      value = ns.normalizeBoolean(value);
    }
    return compare(queryValue, value);
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
        operator = (rule.when.operator || 'AND').toUpperCase(),
        condFn = (operator === 'OR') ? ns.any : ns.all,
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

  ns.actions._styleByUID = function (uid) {
    var head = $('head'),
        styleid = 'stylesfor-' + uid,
        style = $('style#' + styleid);
    if (!style.length) {
      style = $('<style>').attr('id', styleid).appendTo(head);
    }
    return style;
  };

   ns.actions._highlightCSS = function (container, action, opts) {
    var divId = ns.escapeId(container.attr('id')),
        result = '#' + divId + ' {\nXXX\n}\n',
        message = action.message,
        msgRule = '\n\n#' + divId + ':after {\nXXX\n}',
        after,
        color = action.color || '#ff9',
        rules = '  background-color: ' + color + ';';
    result = result.replace('XXX', rules);
    if (typeof message === 'string') {
      after = 'content: "' + message + '";\n';
      after += 'font-weight:bold;';
      msgRule = msgRule.replace('XXX', after);
      result += msgRule;
    }
    return result;
  };

  ns.actions.highlight = function (form, action, opts) {
    var container = ns.fieldDiv(form, action.field),
        divId = ns.escapeId(container.attr('id')),
        styleuid = ns.uuid4(),
        style = ns.actions._styleByUID(styleuid);
    ns.actions.remove_highlights(form, action, opts);
    container.addClass('highlighted-field');
    style.append(ns.actions._highlightCSS(container, action, opts));
    container.attr('data-highlight-style', 'stylesfor-' + styleuid);
  };

  ns.actions.remove_highlights = function (form, action, opts) {
    var container = ns.fieldDiv(form, action.field),
        divId = ns.escapeId(container.attr('id')),
        styleId = container.attr('data-highlight-style');
    if (styleId) {
      $('#' + styleId).remove();
      container.removeAttr('data-highlight-style');
    }
    container.removeClass('highlighted-field');
  };

  return ns;

}(jQuery));
