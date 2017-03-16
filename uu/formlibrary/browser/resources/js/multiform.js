/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */


//nested namespaces for script functions and objects:
if (!window.uu) {
  var uu = {};
}
if (!uu.formlibrary) {
  uu.formlibrary = {};
}
if (!uu.formlibrary.multiform) {
  uu.formlibrary.multiform = {};
}

var $ = $ || jQuery;

// graft mockup widget pattern registry:
uu.hasReg = (window.require) ? window.require.defined('pat-registry') : false;
uu.pReg = (uu.hasReg) ? window.require('pat-registry') : undefined;

/* validator functions: */
uu.formlibrary.multiform.val_int_req = function(input, value) {
  return (/^[\-]?(\d+|(\d{1,2},)?((\d{3}),)*(\d{3}))$/).test(value); /* required integer */
};

uu.formlibrary.multiform.val_int = function(input, value) {
  return (/^([\-]?(\d+|(\d{1,2},)?((\d{3}),)*(\d{3})))?$/).test(value); /* optional integer */
};

uu.formlibrary.multiform.val_dec_req = function(input, value) {
  return (/^(\d+([.]\d+)?|([.]\d+))$/).test(value); /* required float */
};

uu.formlibrary.multiform.val_dec = function(input, value) {
  return (/^([\-]?(\d+([.]\d+)?|([.]\d+)))*$/).test(value); /*optional float */
};

uu.formlibrary.multiform.val_date_req = function(input, value) {
  return (Date.parse(value) != null); /* is date parsable? */
};

uu.formlibrary.multiform.val_date = function(input, value) {
  if (value === '') {
    return true; /*optional field*/
  }
  return uu.formlibrary.multiform.val_date_req(input, value);
};

uu.formlibrary.multiform.formids = function() {
  var ids = [];
  $("form.formrow").each(function(idx){
    ids.push(this.id);
    });
  return ids;
};

uu.formlibrary.multiform.getform = function(id) {
  var o = {},
      excludedInput = function (idx, el) {
        var input = $(el),
            classBlacklist = ['picker__input'];
        return classBlacklist.some(function (e, i, arr) {
          return input.hasClass(e);
        });
      },
      excludedFieldname = function (fieldName) {
        if (fieldName.split('empty-marker').length == 2) {
          return true;
        }
        if (fieldName.split('-calendar').length > 1) {
          return true;
        }
        return false;
      },
      form = $("#"+id),
      inputs = $(
        "input, textarea, select.choice-field, select.set-field",
        form
      );

  // get UID for the row/record:
  o.record_uid = form[0].id;

  // jQuery filter out excluded by class:
  inputs = inputs.not(excludedInput);

  inputs.each(function (idx, el) {
    var input = $(el),
        multivalued = false,
        inputName = input.attr('name') || '',
        tagName = input[0].tagName,
        fieldName;
    if (inputName.indexOf('~') === -1) {
      return;  // not an input for a field
    }
    fieldName = inputName.split('~')[1].split(':')[0].split('.').pop();
    // filter on non-sense field names:
    if (excludedFieldname(fieldName)) {
      return;
    }
    // exclude plone.protect token:
    if (input.attr('name') === '_authenticator') return;   // plone.protect

    if (tagName == 'INPUT') {
      if (input.attr('type') == 'radio') {
        if (input[0].checked) {
          o[fieldName] = input.val();
        }
        return;
      }
      if (input.attr('type') == 'checkbox') {
        multivalued = true;
        if (input.hasClass('bool-field')) {
          o[fieldName] = false; //default...
          if (input[0].checked) {
            o[fieldName] = true;
          }
          return;
        } else {
          if (!input[0].checked) {
            if (Object.keys(o).indexOf(fieldName) === -1) {
              o[fieldName] = [];  // at very least, support an empty set
            }
            return;
          }
        }
      }
      if (input.attr('type') == 'hidden') {
        if (inputName.split(':list').length == 2) {
          multivalued = true;
        }
      }
    }
    if (tagName == 'SELECT') {
      if (input[0].multiple === true) {
        // multi-valued select.set-field:
        o[fieldName] = input.val();
        multivalued = true;
      } else {
        o[fieldName] = input.val();
      }
    } else if ((inputName.split(':list').length == 2) && (multivalued===true)) {
      /* multi-choice field: checkbox, one-by-one, we add checked values */
      if (!o[fieldName]) {
        o[fieldName] = [];
      }
      o[fieldName].push(input.val());
    }
    else {
      o[fieldName] = input.val();
    }
  });
  return o;
};

uu.formlibrary.multiform.formgrid = function() {
  var ids = uu.formlibrary.multiform.formids();
  var result = [];
  for (var i=0; i<ids.length; i++) {
    var form = uu.formlibrary.multiform.getform(ids[i]);
    if (form) {
      result.push(form);
      }
    }
  return result;
};

uu.formlibrary.multiform.formnotes = function() {
  var defval = "Enter any notes pertaining to this period.";
  var v = $('textarea.entry_notes').val();
  if (v == defval) {
    return "";
  }
  return v;
};

/* field get/set helpers, given form/fieldName context */

uu.formlibrary.multiform.getValue = function (form, fieldName) {
  /** TODO */
  return uu.formlibrary.multiform.getform(form.attr('id'))[fieldName];
};

uu.formlibrary.multiform.setValue = function (form, fieldName, value) {
  /** TODO */
};

/* output object bundling form grid data (entries) and entry notes */
uu.formlibrary.multiform.formbundle = function() {
  var o = {};
  o.notes = uu.formlibrary.multiform.formnotes();
  o.entries = uu.formlibrary.multiform.formgrid();
  return o;
};

/* output JSON string of form grid data and change metadata */
uu.formlibrary.multiform.jsonbundle = function() {
  var serialization = JSON.stringify(uu.formlibrary.multiform.formbundle());
  if (JSON.stringify(document.createElement('input').value) === '"null"') {
    serialization = serialization.replace(/["]null["]/gi, '""');
  }
  return serialization;
};


uu.formlibrary.multiform.copybundle = function() {
  var payload = $('#payload');
  payload.val(uu.formlibrary.multiform.jsonbundle());
};

uu.formlibrary.multiform.rowup = function() {
  var btn = $(this);
  var rowitem = btn.parents('li');
  var prev = rowitem.prev();
  if (prev[0] != null) {
    rowitem.insertBefore(prev);
    }
  uu.formlibrary.multiform.refreshbuttons();
};

uu.formlibrary.multiform.rowdown = function() {
  var btn = $(this);
  var rowitem = btn.parents('li');
  var next = rowitem.next();
  if (next[0] != null) {
    rowitem.insertAfter(next);
    }
  uu.formlibrary.multiform.refreshbuttons();
};

uu.formlibrary.multiform.rowdelete = function() {
  var btn = $(this);
  btn.parents('li').remove();
  uu.formlibrary.multiform.rowhandlers();
};

uu.formlibrary.multiform.refreshbuttons = function() {
  $('ol.formrows li div.rowcontrol a.rowup').show();
  $('ol.formrows li div.rowcontrol a.rowdown').show();
  $('ol.formrows li:first div.rowcontrol a.rowup').hide();
  $('ol.formrows li:last div.rowcontrol a.rowdown').hide();
};


uu.formlibrary.multiform.validator_setup = function() {
  if ($.tools.validator) {
    $('div.error').remove();
    $.tools.validator.fn('input.int-field', 'Value must be whole number', uu.formlibrary.multiform.val_int);
    $.tools.validator.fn('input.float-field', 'Value provided must be decimal number', uu.formlibrary.multiform.val_dec);
    $('input.int-field').validator();
    $('input.float-field').validator();
  }
};

uu.formlibrary.multiform.hookup_formevents = function () {
  var formevents = window.formevents,
    _useChange = function (e) {
      /* is discrete choice or date widget's style-hidden input */
      var el = $(e),
        t = el.attr('type'),
        controlledTypes = ['radio', 'checkbox'],
        isSel = (e.tagName || '').toLowerCase() === 'select';
      if (!e.tagName) { console.log(e); }
      if (el.hasClass('pat-type-a-date')) {
        return true; 
      }
      return isSel || controlledTypes.indexOf(t) !== -1;
    },
    core = $('#formcore ol.formrows'),
    forms = $('#formcore form'),
    inputs = $(
      'input, textarea, select.choice-field, select.date-field',
      core
      ).filter(function () { return $(this).attr('type') !== 'hidden'; }),
    notifyOnChange = inputs.filter(function () {return _useChange(this);}),
    notifyOnBlur = inputs.filter(function () { return !_useChange(this); }),
    handler = function () {
      var context = $(this),
        target = $(context.parents('.fielddiv')[0]),
        fieldName = target.attr('id').split('~-')[1],
        isInput = this.tagName.toLowerCase() === 'input',
        inputs = $('input', target).is(':visible'),
        isMulti = isInput && inputs.length > 1,
        getMulti = function () {
          var selected = $('input:checked', target).toArray();
          return selected.map(function (e) { return $(e).val(); });
        },
        eventInfo = {
          form: context.parents('form')[0],
          target: target[0],
          field: fieldName,
          value: isMulti ? getMulti() : context.val(),
          event: 'change'
        },
        blacklist = ['picker__input'],
        ignored = false;
        blacklist.forEach(function (v) {
            if ($(this).hasClass(v)) {
              ignored = true;
            }
          },
          this
        );
      if (!ignored) {
        window.formevents.notify(eventInfo);
      }
    };
  // hookup notification on changes to field values:
  notifyOnChange.change(handler);
  notifyOnBlur.blur(handler);
  // Finally, apply rules to existing forms, as postLoad callback:
  window.formskip.postLoad.push(function () {
    forms.each(function () {
      var form = $(this);
      window.formevents.notify({
        form: form,
        field: '@form',
        event: 'added'
      });
    });
  });
};

uu.formlibrary.multiform.rowhandlers = function(row) {
  var form = $('form.formrow', row);
  // row order and delete control events:
  $('a.rowup, a.rowdown, a.rowdelete').unbind('click');
  $('a.rowup').click(uu.formlibrary.multiform.rowup);
  $('a.rowdown').click(uu.formlibrary.multiform.rowdown);
  $('a.rowdelete').click(uu.formlibrary.multiform.rowdelete);
  uu.formlibrary.multiform.refreshbuttons();
  // if we have mockup, scan for type-a-date pattern:
  if (uu.pReg) {
    uu.pReg.scan(row);
  }
  // validator for numeric fields only, right now:
  uu.formlibrary.multiform.validator_setup();
  // event notification hookups, using formevent.js, if available:
  if (window.formevents) {
    uu.formlibrary.multiform.hookup_formevents(); 
  }
};

uu.formlibrary.multiform._new_row = function (context) {

};

uu.formlibrary.multiform.handle_new_row = function() {
  var num_rows = parseInt($('input.numrows').val(), 10),
      onSuccess = function (responseText) {
        var row = $('<div />').append(responseText).find('ol.formrows li'),
            form = $('form.formrow', row);
        // add form row to existing list:
        $('ol.formrows').append(row);
        // handle this form row (div)'s events: 
        uu.formlibrary.multiform.rowhandlers(row);
        // display fixups for stacked boxes mode:
        uu.formlibrary.multiform.clean_form_display();
        // finally notify form-level 'added' event:
        window.formevents.notify({
          form: form,
          field: '@form',
          event: 'added'
        });
      };
  for (var i=0; i<num_rows; i++) {
    $.ajax({
      url: uu.formlibrary.multiform.new_row_url(),
      success: onSuccess /*callback*/
    });
  }
};

uu.formlibrary.multiform.new_row_url = function() {
  var cachebust = Math.random() * 10000000000000000000;
  return $('input#new_row_url').val() + '?random=' + cachebust;
};

uu.formlibrary.multiform.submit = function(event) {
  var int_validates = true,
    date_validates = true,
    float_validates = true,
    saveManager = multiform.save,
    isSubmit = uu.formlibrary.multiform.last_action === 'save_submit',
    note = $("#coredata input[type=submit][clicked=true]").val() || 'Saved data';
  /* validate first, only submit if no errors */
  if ($('input.int-field').length>0) {
    int_validates = $('input.int-field').data('validator').checkValidity();
  }
  if ($('input.float-field').length>0) {
    float_validates = $('input.float-field').data('validator').checkValidity();
  }
  if (int_validates && float_validates && date_validates) {
    uu.formlibrary.multiform.copybundle(); /* serialize JSON to hidden 'payload' input */
    // Create a application/x-www-form-urlencoded encoded serialization,
    // save locally, attempt sync to server over AJAX using SaveManager:
    saveManager.save($('#coredata').serialize(), isSubmit, note);
    return false;
  } else {
    alert('Please correct input errors and then try saving again.');
    return false;
  }
};


uu.formlibrary.multiform.clean_form_display = function() {
  /* clean stacked-format form field divs, if any inserting
     vertical separation div after every three fields to 
     ensure clean row look.
  */
  var forms = $('form.formrow'),
    colCount = parseInt(forms.attr('data-stacked-columns') || '3', 10),
    colWidth = '30%';
  if (colCount !== 3) {
    colWidth = '' + (Math.floor(100 / colCount) - colCount) + '%';
  }
  // mark required field div:
  $('input.required').parents('div.fielddiv').addClass('required');
  // temporary place to re-classify divider divs:
  $('input.dividerfield-field').parents('div.fielddiv').addClass('divider');
  // iterate through forms and set up pseudo-columns:
  forms.each(function (idx) {
    var form = $(this),
      formdiv = form.children('div.singlerowform'),
      fieldDivs = formdiv.find('div.fielddiv'),
      normalFields = fieldDivs.not('.divider'),
      colIdx = 0;
    normalFields.css({'width': colWidth});
    if (colCount > 3) {
      normalFields.css({'font-size': '90%'});
      $('label, input, select', normalFields)
        .not('.picker__input')
        .css({'max-width': '90%'});
      forms.addClass('compact-columns');
    }
    fieldDivs.each(function (idx) {
      var fieldDiv = $(this),
        next;
      if (fieldDiv.hasClass('divider')) {
        colIdx = 0;
        return;
      }
      if ((colIdx + 1) % colCount === 0) {
        next = fieldDiv.next();
        if (next.hasClass('fielddiv') && !next.hasClass('divider')) {
          $('<div class="fakerule" style="border-bottom:1px solid #bbb;padding:1em;margin:1em;clear:both"></div>').insertAfter(fieldDiv);
        }
      }
      colIdx += 1;
    });
  });
  // address side-effects of divider placement possibly adjacent to fake hr:
  $('div.fielddiv.divider').each(function (i) {
    var divider = $(this);
    divider.prev('.fakerule').remove();
    divider.next('.fakerule').remove();
  });
};


$(document).ready(function(){
  $('input#btn-addrow').click(uu.formlibrary.multiform.handle_new_row);
  uu.formlibrary.multiform.rowhandlers();
  $('#coredata input[type=submit]').click(function () {
    uu.formlibrary.multiform.last_action = $(this).attr('name');
  });
  $('#coredata').submit(uu.formlibrary.multiform.submit);
  $('textarea.entry_notes').focus(function() {
    var defval = "Enter any notes pertaining to this period.";
    if ($(this).val() == defval) {
      $(this).val('');
      }
  });
  uu.formlibrary.multiform.clean_form_display(); /* only for stacked; for record divs in DOM at page load */
  multiform.save.loadStatus();  
});



