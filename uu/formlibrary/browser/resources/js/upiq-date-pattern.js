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

  ns.time_formats = {
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
    // UK/Canada little-endian, but allow for middle-endian long dates:
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
    // Continental, South America, etc: little-endian plus big-endian fallback
    'fr-fr': [
      'H',
      'HH',
      'HH.mm',
      'H.mm',
    ],
  };

  ns.parseLocale = function () {
    var remap = {
          // source: target
          'en-us': 'en-us',   // to avoid general en -> en-gb
          'en-ca': 'en-gb',
          'en': 'en-gb'       // excluding USA, English-speaking world like UK
        },
        def = 'fr-fr';  // default to little-endian
    return remap[userLocale] || remap[userLang] || def;
  };

  ns.parse = function (v) {
    var formats = ns.formats[ns.parseLocale()];
    // Avoid ISO format, since that makes Date assume GMT
    v = v.replace(/-/g, '/').replace(/\./g, '/').replace(/,/g, ' ');
    return m(v, formats);
  };

  ns.parsetime = function (v) {
    var formats = ns.time_formats[ns.parseLocale()];
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
    
    var UpiqADate = PickADate.extend({
      name: 'upiq-date',
      trigger: '.pat-upiq-date',
      init: function () {
        var self = this,
            core = new PickADate(this.$el, {}),
            addKey = function (event) {
              self.dateEntry += String.fromCharCode(event.keyCode);
              core.$date.val(self.dateEntry);
              self.dateDirty = true;
              return true;
            },
            clearValue = function (event) {
              self.dateEntry = '';
              self.dateDirty = false;
            },
            normalizeAndSetValue = function () {
              var normalized = '';
              if (self.dateEntry) {
                normalized = parsedate.parse(self.dateEntry);
                if (normalized.toString() === 'Invalid Date') {
                  core.$date.val('Invalid date, please try again');
                  self.dateEntry = '';
                  core.$el.val(self.dateEntry);
                }
                normalized = normalized.toISOString().split('T')[0];
              }
              core.$date.val(normalized);
              core.$el.val(normalized);
              clearValue();  // reset buffer
            },
            considerKey = function (event) {
              var code = event.keyCode,
                  isDigit = (code >= 48 && code <= 57),
                  isAlpha = (code >= 65 && code <= 90),
                  considered = [32, 44, 47, 45];
              return (isDigit || isAlpha || considered.indexOf(code) !== -1);
            },
            ignore = function (event) { return true; },
            keyHandlers = {
              8: clearValue,    // backspace
              13: function (event) {
                normalizeAndSetValue();
                // prevent <Enter> from accidentally submitting form
                event.preventDefault();
                return false;
              },
              16: ignore,       // shift
              17: ignore,       // control
              18: ignore,       // alt
              27: ignore,       // esc
              32: ignore,       // space
              37: ignore,       // cursor...
              38: ignore,
              39: ignore,
              40: ignore,
              46: clearValue,   // del
              173: function (event) {
                addKey({keyCode:45});
              },
              191: function (event) {
                addKey({keyCode:47});
              },
              224: ignore       // command (Apple)
            };
        this.dateDirty = false;
        this.dateEntry = '';
        this.core = core;
        core.$date.on('keydown', function (event) {
          var handler = keyHandlers[event.keyCode] || addKey;
          return handler(event);
        });
        core.$date.on('blur', function (event) {
          if (self.dateDirty) {
            normalizeAndSetValue();
          }
        });
      }
    });

    return UpiqADate;

  }
);

require(['pat-upiq-date']);
