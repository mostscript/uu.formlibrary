/* save manager */

/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

var multiform = (function ($, ns) {

  "use strict";

  // utility functions:
  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };

  ns.SaveManager = function (url, mimeType) {
    
    var localStorage = window.localStorage;

    this.init = function (url, mimeType) {
      this.prefix = 'multiform_save';
      this.attempts = [];   // attempt metadata, usually just last
      this.failures = [];   // failed attempt metadata
      this._status = [];    // status messages
      this.unsavedData = false;   // may be false or string key of unsaved
      this.saveURL = url;
      this.mimeType = mimeType || 'application/x-www-form-urlencoded';
      this.lastKnownGood = null;
      this.pathname = window.location.pathname;
      this.loadConfig();    // from local storage, if applicable
    };
    
    this.toJSON = function () {
      return {
        attempts: this.attempts,
        failures: this.failures,
        unsavedData: this.unsavedData,
        lastKnownGood: this.lastKnownGood
      };
    };

    this.configKey = function () {
      /** page specific configuration key to keep storage page-specific,
        * and avoid incidental shared state across forms, as such could
        * be a problem for retry of failed save.
        */
      return 'multiform_save_manager' + this.pathname;
    };

    this.loadConfig = function () {
      var config = localStorage.getItem(this.configKey());
      if (!config) return;
      config = JSON.parse(config);
      this.attempts = (config.attempts) ? config.attempts : this.attempts;
      this.failures = (config.failures) ? config.failures : this.failures;
      if (config.unsavedData !== undefined) {
        this.unsavedData = config.unsavedData;
      }
      this.lastKnownGood = config.lastKnownGood || null;
    };

    this.syncConfig = function () {
      localStorage.setItem(this.configKey(), JSON.stringify(this));
    };

    this.retryLastFailedSave = function () {
      var lastAttempt = this.failures.slice(-1).pop(),
          tid = lastAttempt.tid,
          key = this.dataKey(tid),
          isSubmit = lastAttempt.isSubmit || false,
          data = localStorage.getItem(key);
      this.clearStatus();
      this.attemptSync(data, tid, isSubmit, 'Retry save to server');
    };

    this.userDismiss = function (url) {
      var target = $('#multiform-status'),
          core = $('#formcore');
      target.empty();
      if (url) {
        window.location.href = url;
      }
      core.removeClass('pending-ack');
    };

    this.userNotify = function (isSubmit) {
      /** notify user via DOM of state of affairs, if needed */
      var target = $('#multiform-status'),
          self = this,
          addRetryButton = function () {
            var msg = 'Retry saving to server',
                btn = $(
                  '<input class="retry-save" type="button" value="' + msg + '">'
                ).appendTo(target);
            btn.click(function () {
              target.empty().html('Retrying now...');
              self.retryLastFailedSave();
            });
          };
      if (!target.length) return;
      target.empty();
      $('#formcore').addClass('pending-ack');  // pending acknowledgement
      // apply all messages from status:
      this._status.forEach(function (pair) {
        var classname = pair[1],
            msg = pair[0],
            messageDiv = $('<div class="save-status">').appendTo(target);
        if (classname) {
          messageDiv.addClass(classname);
        }
        messageDiv.html(msg);
      });
      if (this.unsavedData) {
        target.removeClass('success');
        // notify: add message and actionable retry button to target TODO TODO
        addRetryButton();
      } else {
        // simple 'ok' button to dismiss:
        target.addClass('success');
        $('<input type="button" class="ack" value="OK" />')
          .appendTo(target)
          .click(function () {
            var url = (isSubmit) ? './' : undefined;
            self.userDismiss(url);
          });
      }
      target.get(0).scrollIntoView();
    };

    this.allDataKeys = function () {
      var i, k, result = [];
      for (i = 0; i < localStorage.length; i++) {
        k = localStorage.key(i);
        if (k.indexOf(this.prefix) === 0) {
          result.push(k);
        }
      }
      return result;
    };

    this.dataKey = function (tid) {
      return this.prefix + '_' + tid;
    };

    this.getTID = function () {
      /** get uuid based transaction id */
      return ns.uuid4();
    };

    this.saveLocal = function (data, tid) {
      var key = this.dataKey(tid);
      localStorage.setItem(key, data);
    };

    this.removeStaleData = function (currentTid) {
      /** any stored data that does not match (last) currentTid gets trashed */
      var current = this.dataKey(currentTid),
          allKeys = this.allDataKeys();
      allKeys.forEach(function (k) {
          if (k !== current) {
            localStorage.removeItem(k);
          }
        },
        this
      );
    };

    this.clearStatus = function (msg) {
      this._status = [];
    };

    this.addStatus = function (msg, classname) {
      this._status.push([msg, classname]);
    };

    this.onError = function (attempt, status, error) {
      $('#formcore').addClass('failed-save');
      this.failures.push(attempt);
      this.unsavedData = this.dataKey(attempt.tid);
      if (status === 'Previous error') {
        this.addStatus(error, 'heading');
        this.addStatus(
          'Data from a previous attempt to save was not successfully ' +
          'saved to the server; please retry saving before continuing.',
          'detail'
        );
      } else {
        this.addStatus('<strong>WARNING</strong>: ' +
                        'Some data was not saved to the server, but was ' +
                        'preserved in your web browser local storage.  ' +
                        'You can retry saving by clicking "Retry save" ' +
                        'below.', 'warning');
      } 
      this.syncConfig();
      this.userNotify();
    };

    this.attemptSync = function (data, tid, isSubmit, note) {
      var attempt = {
            tid: tid,
            time: (new Date()).valueOf(),
            action: note,
            isSubmit: isSubmit,
            synced: false
          },
          self = this;
      this.attempts.push(attempt);
      // Try ajax: callback for success is to remove attempt, callback for
      $.ajax({
        url: this.saveURL,
        type: 'POST',
        data: data,
        contentType: this.mimeType,
        dataType: 'json',
        success: function (response) {
          var attemptIdx = self.attempts.indexOf(attempt);
          self.attempts.splice(attemptIdx, 1);  // good sync, remove from limbo
          self.removeStaleData(tid);
          self.failures = [];             // clear failures list
          self.unsavedData = false;
          $('#formcore').removeClass('failed-save');
          self.lastKnownGood = self.dataKey(tid);
          self.addStatus('Data successfully saved to server.', 'heading');
          if (isSubmit) {
            self.addStatus(
              'Form successfully submitted, click ok to leave editing.',
              'info'
            );
          }
          ((response || {}).messages || []).forEach(function (msg) {
            self.addStatus(msg, 'detail');
          });
          self.syncConfig();
          self.userNotify(isSubmit);
        },
        error: function (xhr, status, error) {
          self.onError(attempt, status, error);
        }
      });
    };

    this.save = function (data, isSubmit, note) {
      var tid = this.getTID();
      if (typeof data !== 'string') {
        throw new TypeError('Incorrect data type, must be string');
      }
      this.clearStatus();
      this.saveLocal(data, tid);
      this.attemptSync(data, tid, isSubmit, note);
    };

    this.loadStatus = function () {
      var msg = 'There was a previous failed save attempt.';
      if (this.failures.length) {
        this.onError(this.failures[0], 'Previous error', msg);
      }
    };

    // remove html base tag, if any:
    $('base').remove();
    this.init(url, mimeType);

  };

  ns.save = new ns.SaveManager('@@form_save');

  return ns;

}(jQuery, multiform || {}));

