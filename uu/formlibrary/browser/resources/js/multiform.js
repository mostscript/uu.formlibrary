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
    var o = {};
    var form = $("#"+id);
    o.record_uid = form[0].id;
    var inputs = $("input, textarea, select.choice-field, select.date-field", form);
    for (var i=0; i<inputs.length; i++) {
        var multivalued = false;
        var input = $(inputs[i]);
        var fieldname = input.attr('name').split('~')[1].split(':')[0].split('.').pop();
        if (fieldname.split('empty-marker').length == 2) {
            continue;
            }
        if (fieldname.split('-calendar').length > 1) {
            continue;
            }
        var element = input[0].tagName;
        if (element == 'INPUT') {
            if (input.attr('type') == 'radio') {
                if (input[0].checked) {
                    o[fieldname] = input.attr('value');
                    }
                continue;
                }
            if (input.attr('type') == 'checkbox') {
                multivalued = true;
                if (input.hasClass('bool-field')) {
                    o[fieldname] = false; //default...
                    if (input[0].checked) {
                        o[fieldname] = true;
                        }
                    continue;
                    }
                else {
                    if (!input[0].checked) {
                        continue;
                        }
                    }
            }
            if (input.attr('type') == 'hidden') {
                if (input.attr('name').split(':list').length == 2) {
                    multivalued = true;
                    }
            }
        }
        if (element == 'SELECT') {
            if (input[0].multiple === true) {
                multivalued = true;
                }
        }
        if ((input.attr('name').split(':list').length == 2) && (multivalued===true)) {
            /* multi-choice field */
            if (!o[fieldname]) {
                o[fieldname] = [];
                }
            o[fieldname].push(input.attr('value'));
            }
        else {
            o[fieldname] = input.attr('value');
            }
        }
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
        $.tools.validator.fn('.int-field.required', 'Enter REQUIRED whole number', uu.formlibrary.multiform.val_int_req);
        $.tools.validator.fn('input.int-field:not(.required)', 'Value must be whole number', uu.formlibrary.multiform.val_int);
        $.tools.validator.fn('.float-field.required', 'Enter REQUIRED (decimal) number value', uu.formlibrary.multiform.val_dec_req);
        $.tools.validator.fn('input.float-field:not(.required)', 'Value provided must be decimal number', uu.formlibrary.multiform.val_dec);
        $.tools.validator.fn('.smartdate-widget.required', 'Enter REQUIRED, correctly formatted date', uu.formlibrary.multiform.val_date_req);
        $.tools.validator.fn('input.smartdate-widget:not(.required)', 'Value must be correctly formatted date', uu.formlibrary.multiform.val_date);
        $('input.int-field').validator();
        $('input.smartdate-widget').validator();
        $('input.float-field').validator();
    }
};

uu.formlibrary.multiform.hookup_formevents = function () {
    var formevents = window.formevents,
        isDiscrete = function (e) {
            var el = $(e),
                t = el.attr('type'),
                controlledTypes = ['radio', 'checkbox'],
                isSel = (e.tagName || '').toLowerCase() === 'select';
            if (!e.tagName) { console.log(e); }
            return isSel || controlledTypes.indexOf(t) !== -1;
        },
        core = $('#formcore ol.formrows'),
        inputs = $(
            'input, textarea, select.choice-field, select.date-field',
            core
            ).filter(function () { return $(this).attr('type') !== 'hidden'; }),
        notifyOnChange = inputs.filter(function () {return isDiscrete(this);}),
        notifyOnBlur = inputs.filter(function () { return !isDiscrete(this); }),
        handler = function () {
            var context = $(this),
                target = $(context.parents('.fielddiv')[0]),
                fieldname = target.attr('id').split('~-')[1],
                isInput = this.tagName.toLowerCase() === 'input',
                isMulti = isInput && $('input', target).length > 1,
                getMulti = function () {
                    var selected = $('input:checked', target).toArray();
                    return selected.map(function (e) { return $(e).val(); });
                },
                eventInfo = {
                    form: context.parents('form')[0],
                    target: target[0],
                    field: fieldname,
                    value: isMulti ? getMulti() : context.val(),
                    event: 'change'
                };
            window.formevents.notify(eventInfo);
        };
    notifyOnChange.change(handler);
    notifyOnBlur.blur(handler);
};

uu.formlibrary.multiform.rowhandlers = function() {
    // events:
    $('a.rowup, a.rowdown, a.rowdelete').unbind('click');
    $('a.rowup').click(uu.formlibrary.multiform.rowup);
    $('a.rowdown').click(uu.formlibrary.multiform.rowdown);
    $('a.rowdelete').click(uu.formlibrary.multiform.rowdelete);
    uu.formlibrary.multiform.refreshbuttons();
    /* order important: validator, smartdate both use keyboard events */
    uu.formlibrary.multiform.validator_setup();
    if (window.smartdate) {
        smartdate.hookups();
    }
    // event notification hookups, using formevent.js, if available:
    if (window.formevents) {
        uu.formlibrary.multiform.hookup_formevents(); 
    }
};

uu.formlibrary.multiform.handle_new_row = function() {
    var num_rows = parseInt($('input.numrows').val(), 10),
        onSuccess = function (responseText) {
            var row = $('<div />').append(responseText).find('ol.formrows li');
            $('ol.formrows').append(row);
            uu.formlibrary.multiform.rowhandlers(); /* hookup for new rows needed */
            uu.formlibrary.multiform.clean_form_display(); /* stacked display fixups */
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

uu.formlibrary.multiform.submit = function() {
    var int_validates = true;
    var date_validates = true;
    var float_validates = true;
    /* validate first, only submit if no errors */
    if ($('input.int-field').length>0) {
        int_validates = $('input.int-field').data('validator').checkValidity();
    }
    if ($('input.smartdate-widget').length>0) {
        date_validates = $('input.smartdate-widget').data('validator').checkValidity();
    }
    if ($('input.float-field').length>0) {
        float_validates = $('input.float-field').data('validator').checkValidity();
    }
    if (int_validates && float_validates && date_validates) {
        uu.formlibrary.multiform.copybundle(); /* serialize JSON to hidden 'payload' input */
        //$('form#coredata').submit(); /* submit the form containing the payload */
        return true;
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
          $('label, input, select', normalFields).css({'max-width': '90%'});
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
    $('#coredata').submit(uu.formlibrary.multiform.submit);
    $('textarea.entry_notes').focus(function() {
        var defval = "Enter any notes pertaining to this period.";
        if ($(this).val() == defval) {
            $(this).val('');
            }
    });
    uu.formlibrary.multiform.clean_form_display(); /* only for stacked; for record divs in DOM at page load */
});



