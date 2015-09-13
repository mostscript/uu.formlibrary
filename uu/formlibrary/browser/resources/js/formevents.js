/**
 *  * formevents.js: field/widget change notification / event dispatch
 *   * (c) 2015 The University of Utah / MIT licensed.
 *    */

/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */


var formevents = (function () {

  var ns = {};

  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };

  // subscriber registry data:
  ns.subscriberIds = [];  // keeps order, first registered, first used
  ns.subscribers = {};
  ns.fieldSubscribers = {};

  ns.subscribe = function subscribe(opts) {
    var uid = ns.uuid4();
    if (!opts || !opts.field || !opts.callback) {
      throw new Error('Missing subscription options');
    }
    opts.event = opts.event || 'change';
    ns.subscribers[uid] = opts;
    ns.subscriberIds.push(uid);
    if (!ns.fieldSubscribers[opts.field]) {
      ns.fieldSubscribers[opts.field] = [];
    }
    ns.fieldSubscribers[opts.field].push(uid);
  };
  
  ns.notify = function notify(opts) {
    /**
     * Notify event for field, or specify {field: '@form'} for form-level
     * event; all field-level events require a value.  Generally assumed
     * that following options are provided on notify:
     * {
     *   form: formElement,
     *   target: fieldDivElement,
     *   field: 'some_field_name_here',
     *   value: 'Yes',
     *   event: 'change'
     * }
     */
    // Options object with form is necessary:
    if (!opts || !opts.form) return;
    // return if incomplete or ambiguous field/form specified:
    if (!opts.field) return;
    // return if field event has no value on which to act:
    if (opts.value == null && opts.field !== '@form') return;
    // Get event or default:
    opts.event = opts.event || 'change';
    opts.target = opts.target || opts.form;
    // Check for subscribers, by fieldname, if event type match, run callback:
    (ns.fieldSubscribers[opts.field] || []).forEach(function (subscriberUID) {
      var subscriber = ns.subscribers[subscriberUID];
      if (opts.event === subscriber.event) {
        subscriber.callback(opts);
      }
    });
  };

  return ns;

}());

