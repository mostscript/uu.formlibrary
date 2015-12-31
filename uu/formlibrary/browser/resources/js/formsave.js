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

  ns.SaveManager = function () {
    
    var localStorage = window.localStorage;

    this.init = function (url, mimeType) {
      this.prefix = 'multiform_save';
      this.attempts = [];   // attempt metadata, usually just last
      this.failures = [];   // failed attempt metadata
      this._status = [];    // status messages
      this.unsavedData = false;   // may be false or string key of unsaved
      this.saveURL = url;
      this.mimeType = mimeType || 'application/x-www-form-urlencoded';
      this.loadConfig();    // from local storage, if applicable
    };
    
    this.toJSON = function () {
      return {
        attempts: this.attempts,
        failures: this.failures,
        unsavedData: this.unsavedData
      };
    };

    this.loadConfig = function () {
      var config = localStorage.getItem('multiform_save_manager');
      if (!config) return;
      config = JSON.parse(config);
      this.attempts = (config.attempts) ? config.attempts : this.attempts;
      this.failures = (config.failures) ? config.failures : this.failures;
      if (config.unsavedData !== undefined) {
        this.unsavedData = config.unsavedData;
      }
    };

    this.syncConfig = function () {
      localStorage.setItem('multiform_save_manager', JSON.stringify(this));
    };

    this.retryLastFailedSave = function () {
      var lastAttempt = this.failures.slice(-1).pop(),
          tid = lastAttempt.tid,
          key = this.dataKey(tid),
          data = localStorage.getItem(key);
      this.attemptSync(data, tid, 'Retry save to server');
    };

    this.notifyState = function () {
      /** notify user via DOM of state of affairs, if needed */
      var target = $('#multiform-status'),
          self = this,
          addRetryButton = function () {
            var msg = 'Retry saving to server',
                btn = $(
                  '<input class="retry-save" type="button" value="' + msg + '">'
                ).appendTo(target);
            btn.click(function () {
              self.retryLastSave();
            });
          };
      if (!target.length) return;
      target.empty();
      // apply all messages from status:
      this._status.forEach(function (msg) {
        var messageDiv = $('<div class="save-status">').appendTo(target);
        messageDiv.html(msg);
      });
      if (this.unsavedData) {
        // notify: add message and actionable retry button to target TODO TODO
        addRetryButton();
      }
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
      allDataKeys.forEach(function (k) {
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

    this.addStatus = function (msg) {
      this._status.push(msg);
    };

    this.attemptSync = function (data, tid, note) {
      var attempt = {
            tid: tid,
            time: (new Date()).valueOf(),
            action: note,
            synced: false
          },
          self = this;
      this.attempts.push(attempt);
      // Try ajax: callback for success is to remove attempt, callback for
      $.ajax({
        url: this.saveURL,
        type: 'POST',
        data: data,
        dataType: this.mimeType,
        success: function (response) {
          self.attempts.remove(attempt);  // good sync, it's all good
          self.removeStaleData(tid);
          self.failures = [];             // clear failures list
          self.unsavedData = false;
          self.addStatus('Data saved locally, successfully saved to server');
          self.syncConfig();
        },
        error: function (xhr, status, error) {
          self.failures.push(attempt);
          self.unsavedData = self.dataKey(tid);
          self.addStatus('<strong class="warning">WARNING</strong>: ' +
                         'Some data was not saved to the server, but was ' +
                         'preserved in your web browser local storage.  ' +
                         'You can retry saving by clicking "Retry save" ' +
                         'below.');
          self.syncConfig();
        }
      });
    };

    this.save = function (data, note) {
      var tid = this.getTID();
      if (typeof data !== 'string') {
        throw new TypeError('Incorrect data type, must be string');
      }
      this.clearStatus();
      this.saveLocal(data, tid);
      this.attemptSync(data, tid, note);
    };

    this.init();

  };

  ns.save = new ns.SaveManager();

  return ns;

}(jQuery, multiform || {}));

