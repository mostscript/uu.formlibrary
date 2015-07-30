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

var jq = jQuery;


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
    jq("form.formrow").each(function(idx){
        ids.push(this.id);
        });
    return ids;
};

uu.formlibrary.multiform.getform = function(id) {
    var o = {};
    var form = jq("#"+id);
    o.record_uid = form[0].id;
    var inputs = jq("input, textarea, select.choice-field, select.date-field", form);
    for (var i=0; i<inputs.length; i++) {
        var multivalued = false;
        var input = jq(inputs[i]);
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
    var v = jq('textarea.entry_notes').val();
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
    var payload = jq('#payload');
    payload.val(uu.formlibrary.multiform.jsonbundle());
};

uu.formlibrary.multiform.rowup = function() {
    var btn = jq(this);
    var rowitem = btn.parents('li');
    var prev = rowitem.prev();
    if (prev[0] != null) {
        rowitem.insertBefore(prev);
        }
    uu.formlibrary.multiform.refreshbuttons();
};

uu.formlibrary.multiform.rowdown = function() {
    var btn = jq(this);
    var rowitem = btn.parents('li');
    var next = rowitem.next();
    if (next[0] != null) {
        rowitem.insertAfter(next);
        }
    uu.formlibrary.multiform.refreshbuttons();
};

uu.formlibrary.multiform.rowdelete = function() {
    var btn = jq(this);
    btn.parents('li').remove();
    uu.formlibrary.multiform.rowhandlers();
};

uu.formlibrary.multiform.refreshbuttons = function() {
    jq('ol.formrows li div.rowcontrol a.rowup').show();
    jq('ol.formrows li div.rowcontrol a.rowdown').show();
    jq('ol.formrows li:first div.rowcontrol a.rowup').hide();
    jq('ol.formrows li:last div.rowcontrol a.rowdown').hide();
};


uu.formlibrary.multiform.validator_setup = function() {
    if (jq.tools.validator) {
        jq('div.error').remove();
        jq.tools.validator.fn('.int-field.required', 'Enter REQUIRED whole number', uu.formlibrary.multiform.val_int_req);
        jq.tools.validator.fn('input.int-field:not(.required)', 'Value must be whole number', uu.formlibrary.multiform.val_int);
        jq.tools.validator.fn('.float-field.required', 'Enter REQUIRED (decimal) number value', uu.formlibrary.multiform.val_dec_req);
        jq.tools.validator.fn('input.float-field:not(.required)', 'Value provided must be decimal number', uu.formlibrary.multiform.val_dec);
        jq.tools.validator.fn('.smartdate-widget.required', 'Enter REQUIRED, correctly formatted date', uu.formlibrary.multiform.val_date_req);
        jq.tools.validator.fn('input.smartdate-widget:not(.required)', 'Value must be correctly formatted date', uu.formlibrary.multiform.val_date);
        jq('input.int-field').validator();
        jq('input.smartdate-widget').validator();
        jq('input.float-field').validator();
    }
};

uu.formlibrary.multiform.rowhandlers = function() {
    jq('a.rowup, a.rowdown, a.rowdelete').unbind('click');
    jq('a.rowup').click(uu.formlibrary.multiform.rowup);
    jq('a.rowdown').click(uu.formlibrary.multiform.rowdown);
    jq('a.rowdelete').click(uu.formlibrary.multiform.rowdelete);
    uu.formlibrary.multiform.refreshbuttons();
    /* order important: validator, smartdate both use keyboard events */
    uu.formlibrary.multiform.validator_setup();
    if (window.smartdate) {
        smartdate.hookups();
    }
};

uu.formlibrary.multiform.handle_new_row = function() {
    var num_rows = parseInt(jq('input.numrows').val(), 10),
        onSuccess = function (responseText) {
            var row = jq('<div />').append(responseText).find('ol.formrows li');
            jq('ol.formrows').append(row);
            uu.formlibrary.multiform.rowhandlers(); /* hookup for new rows needed */
            uu.formlibrary.multiform.clean_form_display(); /* stacked display fixups */
        };
    for (var i=0; i<num_rows; i++) {
        jq.ajax({
            url: uu.formlibrary.multiform.new_row_url(),
            success: onSuccess /*callback*/
        });
    }
};

uu.formlibrary.multiform.new_row_url = function() {
    var cachebust = Math.random() * 10000000000000000000;
    return jq('input#new_row_url').val() + '?random=' + cachebust;
};

uu.formlibrary.multiform.submit = function() {
    //console.log(JSON.stringify(uu.formlibrary.multiform.formbundle()));
    var int_validates = true;
    var date_validates = true;
    var float_validates = true;
    /* validate first, only submit if no errors */
    if (jq('input.int-field').length>0) {
        int_validates = jq('input.int-field').data('validator').checkValidity();
    }
    if (jq('input.smartdate-widget').length>0) {
        date_validates = jq('input.smartdate-widget').data('validator').checkValidity();
    }
    if (jq('input.float-field').length>0) {
        float_validates = jq('input.float-field').data('validator').checkValidity();
    }
    if (int_validates && float_validates && date_validates) {
        uu.formlibrary.multiform.copybundle(); /* serialize JSON to hidden 'payload' input */
        //jq('form#coredata').submit(); /* submit the form containing the payload */
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
    var forms = jq('form.formrow'),
        colCount = parseInt(forms.attr('data-stacked-columns') || '3', 10),
        colWidth = '30%';
    if (colCount !== 3) {
      colWidth = '' + (Math.floor(100 / colCount) - colCount) + '%';
    }
    for (var i=0; i<forms.length; i++) {
        var form = jq(forms[i]);
        var formdiv = form.children('div.singlerowform');
        var fielddivs = formdiv.find('div.fielddiv');
        jq('.fielddiv', form).css({'width': colWidth});
        if (colCount > 3) {
          fielddivs.css({'font-size': '90%'});
          jq('label, input, select', fielddivs).css({'max-width': '90%'});
        }
        for (var j=0; j<fielddivs.length; j++) {
            if ((j+1) % colCount === 0) {
                var fielddiv = jq(fielddivs[j]);
                if (fielddiv.next().hasClass('fielddiv')) {
                    jq('<div style="border-bottom:1px solid #bbb;padding:1em;margin:1em;clear:both"></div>').insertAfter(fielddiv);
                }
            }
        }
    }
};


jq(document).ready(function(){
    jq('input#btn-addrow').click(uu.formlibrary.multiform.handle_new_row);
    uu.formlibrary.multiform.rowhandlers();
    jq('#coredata').submit(uu.formlibrary.multiform.submit);
    jq('textarea.entry_notes').focus(function() {
        var defval = "Enter any notes pertaining to this period.";
        if (jq(this).val() == defval) {
            jq(this).val('');
            }
    });
    uu.formlibrary.multiform.clean_form_display(); /* only for stacked; for record divs in DOM at page load */
});



