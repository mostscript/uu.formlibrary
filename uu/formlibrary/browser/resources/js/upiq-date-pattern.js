var define, require;

define('parsedate', ['moment'], function (moment) {
  /** sensible date-parsing of human-entered date strings, using moment
   *  ALL TIMES UTC for sanity!
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


define('mockup-patterns-upiq-date',[
  'jquery',
  'mockup-patterns-pickadate',
  'parsedate'
], function($, PickADate, parsedate) {
  'use strict';

  var UpiqADate = PickADate.extend({
    name: 'upiq-date',
    init: function() {
      UpiqADate.__super__.init.call(this);
      var self = this,
          value = self.$el.val().split(' '),
          dateValue = value[0] || '',
          timeValue = value[1] || '';

      if (self.options.date === false) {
        timeValue = value[0];
      }

      if (self.options.date !== false) {
        self.$date_entry = $('<input type="text" />').prependTo(self.$wrapper.find('.'+self.options.classDateWrapperName));
        self.$date_entry.addClass('pattern-upiq-date-text-entry');
        self.$date_entry.val(dateValue);
        self.$date_entry.on('blur', function (e) {
          var text_value = self.$date_entry.val().toLowerCase();
          var date_value = '';
          if (text_value) {
            var m_value = parsedate.parse(text_value);
            if (m_value) {
              if (self.options.timezone !== null) {
                m_value.zone(self.options.timezone);
              } else {
                m_value.local();
              }
              // Convert to unix time with ms
              date_value = m_value.format('YYYY-MM-DD');
            }
          }
          self.$date.pickadate('picker').set('select', date_value, {format: 'yyyy-mm-dd'});
          self.updateValue();
          self.$date_entry.hide();
          self.$date.show();
        });
        self.$date_entry.hide();
        self.$date.on('keydown', function (event) {
          if ((event.keyCode >= 48 && event.keyCode <= 57) ||
              (event.keyCode >= 65 && event.keyCode <= 90)) {
            self.$date_entry.show().focus().val(String.fromCharCode(event.keyCode));
            self.$date.hide();
            event.stopPropagation();
            return false;
          }
          return true;
        });
        self.$date_entry.on('keydown', function (event) {
          if (event.keyCode == 13) {
            self.$date_entry.blur();
            self.$date.focus();
            event.stopPropagation();
            return false;
          }
          return true;
        });
      }
      if (self.options.time !== false) {
        self.$time_entry = $('<input type="text" />').prependTo(self.$wrapper.find('.'+self.options.classTimeWrapperName));
        self.$time_entry.addClass('pattern-upiq-time-text-entry');
        self.$time_entry.val(timeValue);
        self.$time_entry.on('blur', function (e) {
          var text_value = self.$time_entry.val().toLowerCase();
          var time_value = '';
          if (text_value) {
            var m_value = parsedate.parsetime(text_value);
            if (m_value) {
              time_value = m_value.format('HH:mm');
            }
          }
          self.$time.pickatime('picker').set('select', time_value, {format: 'HH:i'});
          // Only reshow picker if blanked
          if (time_value === '') {
            self.$time_entry.hide();
            self.$time.pickatime('picker').clear().close();
            self.$time.show();        
          }
          self.updateValue();
        });
        self.$time_entry.hide();
        self.$time.on('keydown', function (event) {
          if ((event.keyCode >= 48 && event.keyCode <= 57) ||
              (event.keyCode >= 65 && event.keyCode <= 90)) {
            self.$time_entry.show().focus().val(String.fromCharCode(event.keyCode));
            self.$time.hide();
            event.stopPropagation();
            return false;
          }
          return true;
        });
        self.$time_entry.on('keydown', function (event) {
          if (event.keyCode == 13) {
            self.$time_entry.blur();
            event.stopPropagation();
            return false;
          }
          return true;
        });
      }
    }
  });

  return UpiqADate;

});

define('mockup-upiq-widgets',[
  'jquery',
  'mockup-registry',
  'mockup-patterns-base',
  'mockup-patterns-pickadate',
  'mockup-patterns-upiq-date',
  'moment',
], function($, Registry, Base) {
  'use strict';

  var UpiqWidgets = Base.extend({
    name: 'upiq-widgets',
    init: function() {
      var self = this;
    }
  });

  // initialize only if we are in top frame
  if (window.parent === window) {
    $(document).ready(function() {
      Registry.scan($('body'));
    });
  }

  return UpiqWidgets;
});

require(["mockup-upiq-widgets"]);
