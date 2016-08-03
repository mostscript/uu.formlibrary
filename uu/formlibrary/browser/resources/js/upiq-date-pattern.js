var define, require;

// shim moment from globals (for Plone 4):
if (window.moment) {
  define('moment', function () {
    return window.moment;
  });
}

define('parsedate', ['moment'], function (moment) {
  /** sensible date-parsing of human-entered date strings, using moment
   */
  "use strict";
  var ns = {};

  var m = moment,
      userLocale = (navigator.language || navigator.userLanguage).toLowerCase(),
      userLang = userLocale.split('-')[0],
      ISO = 'YYYY-MM-DD';

  // moment formats, in order of precidence:
  ns.formats = {
    // keys are exemplar locale (lower-case):
    // USA:
    'en-us': [
      'MMM',
      'MMM DD',
      'MMM YYYY',
      'MMM DD YYYY',
      'MM',
      'MM/DD',
      'MM/DD/YY',
      'MM/DD/YYYY',
      ISO
    ],
    // UK/Canada little-endian, but allow for middle-endian long dates:
    'en-gb': [
      'MMM',
      'DD MMM',
      'MMM YYYY',
      'DD MMM YYYY',
      'MMM DD',
      'MMM YYYY',
      'MMM DD YYYY',
      'MM',
      'DD/MM',
      'DD/MM/YY',
      'DD/MM/YYYY',
      ISO
    ],
    // Continental, South America, etc: little-endian plus big-endian fallback
    'fr-fr': [
      'MMM',
      'DD MMM',
      'MMM YYYY',
      'DD MMM YYYY',
      'MMM DD',
      'MMM YYYY',
      'MMM DD YYYY',
      'MM',
      'DD/MM',
      'DD/MM/YY',
      'DD/MM/YYYY',
      // big-endian fallback covers ISO 8601, China, Germany, etc:
      ISO
    ],
  };

  ns.timeFormats = {
    // keys are exemplar locale (lower-case):
    // USA:
    'en-us': [
      'h a',
      'H',
      'HH',
      'h:mm a',
      'hh:mm a',
      'HH:mm',
      'H:mm'
    ],
    // UK/Canada:
    'en-gb': [
      'H',
      'HH',
      'HH:mm',
      'H:mm',
      'hh:mm a',
      'h:mm a',
      'HH.mm',
      'H.mm',
      'hh.mm a',
      'h.mm a'
    ],
    // Continental, South America, etc:
    'fr-fr': [
      'H',
      'HH',
      'HH.mm',
      'H.mm',
    ],
  };

  ns.normalizedLocale = function (nomap) {
    var loc = userLocale,
        lang = userLang,
        remap = {
          // source: target
          'en-us': 'en-us',   // to avoid general en -> en-gb
          'en-ca': 'en-gb',
          'en': 'en-gb'       // excluding USA, English-speaking world like UK
        },
        def = 'fr-fr';  // default to little-endian
    return (nomap) ? (loc || def) : remap[loc] || remap[lang] || def;
  };

  ns.twelveHour = function () {
    var locale = ns.normalizedLocale(true).toLowerCase(),
        en = locale.indexOf('en') === 0,
        gb = locale.indexOf('gb') !== -1,
        loc = locale.split('-')[1] || '',
        otherCountries = ['ph', 'in', 'eg', 'sa', 'co', 'pk', 'my'];
    if (en && !gb) {
      return true;
    }
    return otherCountries.indexOf(loc) !== -1;
  };

  ns.parse = function (v) {
    var formats = ns.formats[ns.normalizedLocale()];
    // Avoid ISO format, since that makes Date assume GMT
    v = v.replace(/-/g, '/').replace(/\./g, '/').replace(/,/g, ' ');
    return m(v, formats);
  };

  ns.parsetime = function (v) {
    var formats = ns.timeFormats[ns.normalizedLocale()];
    return m(v, formats);
  };

  return ns;

});


define(
  'pat-upiq-date',
  [
    'jquery',
    'pat-base',
    'mockup-patterns-pickadate',
    'parsedate'
  ],
  function ($, base, PickADate, parsedate) {
    'use strict';
  
    var EnhancedPickerAdapter = function EnahncedPickerAdapter(context) {
     
      var self = this,
          // key-buffers for date, time entry:
          dateBuffer = '',
          timeBuffer = '',
          // dateValue is moment object or undefined
          dateValue,
          // timeValue is array of hour, minute integers, or undefined
          timeValue,
          clearDateValue = function (event) {
            dateBuffer = '';
            dateValue = undefined;
            self.$date.attr('placeholder', 'Enter date...');
            self.datePicker.open();
          },
          clearTimeValue = function (event) {
            timeBuffer = '';
            timeValue = undefined;
            self.timePicker.open();
          },
          codeKeys = {
            // tiny applicable subset of keydown/keyup mapped to DOM L3 values
            8:  'Backspace',
            13: 'Enter',
            46: 'Delete'
          },
          twelveHour = parsedate.twelveHour();

      self.commonKeyDown = {
        Enter: function (event) {
          self.sync(event);
          // prevent <Enter> from accidentally submitting form
          event.preventDefault();
          return false;
        }
      };

      self.dateKeyDown = {
        Backspace: clearDateValue,
        Delete: clearDateValue,
        ' ': function (event) { return self.addDateKey(self.keyFor(event)); }
      };

      self.timeKeyDown = {
        Backspace: clearTimeValue,
        Delete: clearTimeValue,
        ' ': function (event) { return self.addTimeKey(self.keyFor(event)); }
      };

      self.init = function (context) {
        var options = context.options,
            useDate = !!options.date,
            useTime = !!options.time,
            key = 'picker';
        // Core pattern is context:
        self.context = context;  // core picker pattern
        // Pattern options:
        self.options = options;
        // Hidden input:
        self.$el = self.context.$el;
        // Picker elements
        self.$date = (useDate) ? self.context.$date : null;
        self.$time = (useTime) ? self.context.$time : null;
        // Fix date, time elements to not be readonly
        self.$date[0].removeAttribute('readonly');
        self.$time[0].removeAttribute('readonly');
        // Pick-a-data model objects:
        self.datePicker = (useDate) ? self.$date.pickadate(key) : undefined;
        self.timePicker = (useTime) ? self.$time.pickatime(key) : undefined;
      };

      self.addDateKey = function (key) {
        dateBuffer += key;
        self.datePicker.close();
        self.$date.val(dateBuffer);
        // return false, or key appears appended dupe after buffer value
        return false;
      };

      self.addTimeKey = function (key) {
        timeBuffer += key;
        self.timePicker.close();
        self.$time.val(timeBuffer);
        // return false, or key appears appended dupe after buffer value
        return false;
      };

      self.dateRepr = function () {
          if (!dateValue) return null;
          return dateValue.toISOString().split('T')[0];
      };

      self.timeRepr = function () {
        var h = timeValue[0],
            m = timeValue[1],
            zeropad2 = function (v) {
              return ((''+v).length === 1) ? '0' + v : '' + v;
            };
        if (!timeValue || timeValue.length < 2) return null;
        return '' + zeropad2(h) + ':' + zeropad2(m);
      };

      self.toString = function () {
        var opts = self.options,
            useDate = !!(opts.date && dateValue && dateValue.isValid()),
            useTime = !!(opts.time && timeValue && timeValue.length >= 2),
            dRep, tRep;
        if (useDate) {
          dRep = self.dateRepr();
        }
        if (useTime) {
          tRep = self.timeRepr();
        }
        // date and time both defined, output combined ISO 8601
        if (useDate && useTime) {
          return dRep + 'T' + tRep;
        }
        // date defined, no time
        if (useDate && !useTime) {
          return dRep;
        }
        // no date, just time, if applicable:
        if (useTime && !useDate) {
          return (opts.date) ? '' : tRep;
        }
        // nothing, nada:
        return '';
      };

      self.parseDate = function () {
        var d;  // to be local moment object, if buffer
        // parse date value, if applicable:
        if (dateBuffer) {
          d = parsedate.parse(dateBuffer);
          if (d.isValid()) {
            dateValue = d;
            self.datePicker.close(true);
          } else {
            // Display validation message as placeholder:
            self.$date.val('');
            self.$date.attr('placeholder', 'Invalid date, please try again');
            // Clear buffer state (but not any previous value)
            dateBuffer = '';
            self.datePicker.open();
            // stop processing:
            return;
          }
        }
      };

      self.parseTime = function () {
        var t;  // if buffer, will be moment object from parsetime ret. val.
        // parse time value, if applicable:
        if (timeBuffer) {
          t = parsedate.parsetime(timeBuffer);
          if (t.isValid()) {
            timeValue = [t.hours(), t.minutes()];
            // close picker if we have a parsed, manually entered date:
            self.timePicker.close(true);
          } else {
            clearTimeValue();
          }
        }
      };

      self.syncDateDisplay = function () {
        var opts = self.options,
            useDate = !!(opts.date && dateValue && dateValue.isValid());

        // re-show date picker if focused, blank (or cleared)
        if (!dateBuffer && event.currentTarget === self.$date[0]) {
            self.$date.val('');
            self.datePicker.clear().open();
        }

        // Sync display of date parsed in input using moment format that
        // should jive with format used by picker:
        if (useDate) {
          // set display value:
          self.$date.val(dateValue.format('LL'));
          // reset buffer:
          dateBuffer = '';
        }
      };

      self.syncTimeDisplay = function () {
        var opts = self.options,
            useTime = !!(opts.time && timeValue && timeValue.length >= 2),
            displayTime;
        
        // re-show time picker if focused, blank (or blanked due to invalid):
        if (!timeBuffer && event.currentTarget === self.$time[0]) {
            self.$time.val('');
            self.timePicker.clear().open();
        }

        if (useTime) {
          if (twelveHour) {
            displayTime = moment(self.timeRepr(), ['H:m']).format('h:mm A');
            // use AP style a.m./p.m. abbreviation to match picker output:
            displayTime = displayTime.replace('AM', 'a.m.').replace('PM', 'p.m.');
          } else {
            // 24h time, ISO fragment with leading zeros:
            displayTime = moment(self.timeRepr(), ['H:m']).format('HH:mm');
          }
          // set display value:
          self.$time.val(displayTime);
          // reset buffer:
          timeBuffer = '';
        }

      };

      self.syncInput = function () {
        // Sync hidden input with full representation:
        if (self.$el && self.$el.length === 1) {
          self.$el.val(self.toString());
        }
      };

      self.sync = function (event) {
        self.parseDate();
        self.parseTime();
        self.syncDateDisplay();
        self.syncTimeDisplay();
        self.syncInput();
      };

      self.keyFor = function (event) {
        /* shim for DOM L3 keyboard event.key values */
        var defaultFormatter = function (e) {
          return String.fromCharCode(e.which);
        };
        if (event.key) return event.key;  // native for all events
        if (event.type !== 'keypress') {
          return codeKeys[event.keyCode] || defaultFormatter(event);
        }
        return defaultFormatter(event);
      };

      self.activateDate = function () {
        // hookup date keyboard entry:
        self.$date.on('keydown keypress', function (event) {
          var key = self.keyFor(event),
              handler;
          if (event.type === 'keydown') {
            // keydown for control, plus preempting picker (e.g. spacebar)
            handler = self.commonKeyDown[key] || self.dateKeyDown[key];
            return (handler) ? handler(event) : true;
          } else {
            // most normal input via keypress
            return self.addDateKey(key);
          }
        });

        // grand escape from picker back to input when input justifies it:
        self.datePicker.$root.on('keypress', function (event) {
          var input = self.keyFor(event);
          self.$date.focus();
          self.addDateKey(input);
          return false;
        });

        // blur should attempt parse, but only when picker not open:
        self.$date.on('blur', function (event) {
          if (!self.datePicker.get('open')) {
            self.sync(event);
          }
          return true;
        });

        // open picker on focus of input if not open already:
        self.$date.on('focus', function (event) {
          if (!self.datePicker.get('open')) {
            self.datePicker.open();
          }
        });

        // set hook callback:
        self.datePicker.on('set', function (event) {
          if (event.select) {
            // parse select into moment, set dateValue
            dateValue = moment(event.select);
            self.syncDateDisplay();
            dateBuffer = '';
            // focus the input after click of select from picker
            setTimeout(function () {
                self.$date.focus();
                self.datePicker.close();
              },
              100
            );
          }
          return true;
        });
      };

      self.activateTime = function () {
        // time keyboard entry:
        self.$time.on('keydown keypress', function (event) {
          var key = self.keyFor(event),
              handler;
          if (event.type === 'keydown') {
            // keydown for control, plus preempting picker (e.g. spacebar)
            handler = self.commonKeyDown[key] || self.timeKeyDown[key];
            return (handler) ? handler(event) : true;
          } else {
            return self.addTimeKey(key);
          }
        });

        // blur of time entry should attempt parse:
        self.$time.on('blur', function (event) {
          if (!self.timePicker.get('open')) {
            self.sync(event);
          }
          return true;
        });

        // open picker on focus of input if not open already:
        self.$time.on('focus', function (event) {
          if (!self.timePicker.get('open')) {
            self.timePicker.open();
          }
        });

        // grand escape from picker back to input when input justifies it:
        self.timePicker.$root.on('keypress', function (event) {
          var input = self.keyFor(event);
          self.$time.focus();
          self.addTimeKey(input);
          return false;
        });

        // set hook callback:
        self.timePicker.on('set', function (event) {
          var h, m;
          if (event.select) {
            // Get hour, minute values from minutes since midnight:
            m = event.select % 60;
            h = Math.floor(event.select / 60);
            // set timeValue array from moment object:
            timeValue = [h, m];
            self.syncTimeDisplay();
            timeBuffer = '';
            // focus the input after click of select from picker
            setTimeout(function () {
                self.$time.focus();
                self.timePicker.close();
              },
              100
            );
          }
          return true;
        });

      };

      self.activate = function () {
        if (self.options.date) {
          self.activateDate();
        }

        if (self.options.time) {
          self.activateTime();
        }

      };

      self.init(context);

      return self;
    };

    var UpiqADate = PickADate.extend({
      name: 'upiq-date',
      trigger: '.pat-upiq-date',
      init: function () {
        /** use core pattern, instantiating adapter will add enhancements */
        var core = new PickADate(this.$el, this.options),
            adapter = new EnhancedPickerAdapter(core);
        adapter.activate();  // make UX enhancements live
      }
    });

    return UpiqADate;

  }
);

require(['pat-upiq-date']);
