if (!this.SFDEBUG) SFDEBUG = true;
if (!this.console) console = function () { this.log = function () {}; return this }();

SF_MOCK_JSON = '{"rows":[{"fieldname":"tests","comparator":"Eq","value":"No"},{"fieldname":"report_back","comparator":"Eq","value":"6/26/2012"},{"fieldname":"_referral_reason","comparator":"Any","value":["Diagnosis / Diagnostic work up","Surgery / Opinion about need for surgery"]},{"fieldname":"referral_type","comparator":"Eq","value":"Verbal via Message Log"}],"operator":"AND"}';

SF_MOCK = JSON.parse(SF_MOCK_JSON);

/** searchform namespace, global functions: */
if (!searchform) {
    // top-level namespace in global:
    var searchform = {};
    
    // global storage for named snippets
    searchform.snippets = {};
    
    searchform.snippets.NEWROW = '<tr>' +
        ' <td class="display-queryop">&nbsp;</td>' +
        ' <td class="fieldspec"></td>' +
        ' <td class="compare"></td>' +
        ' <td class="value"></td>' +
        ' <td class="rowcontrol">' +
        '  <a class="removerow" title="Remove query row">' +
        '   <img src="./delete_icon.png" alt="delete"/>' +
        '  </a>' +
        ' </td>' +
        '</tr>';
    
    searchform.snippets.PLACEHOLDER = '<tr class="placeholder">' +
        ' <td class="noqueries" colspan="5">' + 
        '  <em>There are no queries defined for this filter.</em>' +
        ' </td>' +
        '</tr>';
    
    searchform.datarows = function () {
        var table = jq('table.queries');
        return jq('tr', table).not('tr.headings').not('tr.placeholder');
    };
    
    searchform.toggle_operator = function (evt) {
        var opbuttons = jq('form.record-queries div.queryop-selection');
        searchform.control.operator = jq('input:checked', opbuttons).val();
        searchform.toggle_placeholder();
    };
    
    searchform.toggle_placeholder = function (evt) {
        var rows = searchform.datarows();
        console.log(rows.length);
        var rowcount = rows.length;
        var placeholder = jq('table.queries td.noqueries').parent('tr');
        var opbuttons = jq('form.record-queries div.queryop-selection');
        var td_queryop = jq('td.display-queryop', rows);
        td_queryop.filter(':first').html('&nbsp;');
        // if >2 rows, show operator radio buttons below table:
        if (rowcount >= 2) {
            opbuttons.show();
            var operator = jq('input:checked', opbuttons).val();
            td_queryop.not(':first').text('(' + operator + ')');
        } else {
            opbuttons.hide();
        }
        // placeholder text:
        if ((rowcount == 0) && (placeholder.length == 0)) {
            // no placeholder, but no rows, there should be a placeholder
            jq(searchform.snippets.PLACEHOLDER).appendTo(jq('table.queries'));
        } else if ((rowcount == 0) && (placeholder.length == 1)) {
            // no rows, placeholder already in place
            return;
        } else if (placeholder.length) {
            // rows exist, placeholder visible: remove it
            placeholder.remove();
        }        
    };
    
    searchform.reset_zebra = function () {
        //reset zebra-striping "even" classnames when row count changes
        // visual: zebra-striping, works across browsers by marking class
        jq('table.queries tr:nth-child(1n)').removeClass('even');
        jq('table.queries tr:nth-child(2n)').addClass('even');
    };

    searchform.add_row = function () {
        var table = jq('table.queries');
        var row = jq(searchform.snippets.NEWROW).appendTo(table);
        searchform.toggle_placeholder();
        jq('a.removerow', row).click(function(e) {
            jq(this).parents('table.queries tr').remove();
            searchform.toggle_placeholder();
            searchform.reset_zebra();
        });
        searchform.reset_zebra();
        return row;
    };
    
    searchform.prep_row_for_field_change = function (row) {
        jq('td.compare', row).empty();
        jq('td.value', row).empty();
    };
    
    searchform.row_field = function (row) {
        //given row, get field
        var fieldname = jq('td.fieldspec select option:selected', row).val();
        return searchform.control.fields[fieldname];
    };

    searchform.highlight_errors = function() {
        /**
             highlight_errors(): get global error state array,
             highlight all errors
         */
        var errors = searchform.control.errors,
            q_base = 'table.queries td.fieldspec option:checked',
            q;
        jq.each(errors, function (idx, e) {
            var fieldname = e[0],
                msg = e[1],
                field = searchform.control.fields[fieldname],
                row = field.rows();
            if (jq('div.error', row).length == 0) {
                jq('td.value', row).append(
                    jq('<div class="error" />').text(msg));
            }
        });
    };
    
    searchform.queryvalue = function(row) {
        var radio,
            errors = searchform.control.errors,
            rv = null,
            td = jq('td.value', row),
            field = searchform.row_field(row),
            fieldname = field.name;
        // first try select/multi-select value:
        rv = jq('select', td).val();
        // else, try radio button value:
        radio = jq('input:radio', td);
        if (!rv) rv = jq('input:radio:checked', td).val();
        if ((!rv) && (radio.length)) {
            errors.push([fieldname, 'Required input or choice missing']);
            searchform.highlight_errors();
            return null;
        }
        // lastly, try normal input:
        if (!rv) {
            // notes: value is always required, numeric fields attempt cast
            rv = jq('input', td).val();
            if ((!rv) || (rv.length == 0)) {
                errors.push([fieldname, 'Required input or choice missing']);
                searchform.highlight_errors();
                return null;
            }
            if (field.type == 'Int') {
                rv = parseInt(rv, 10);
                if (rv == NaN) {
                    errors.push([fieldname, 'Invalid input, value not a number']);
                    searchform.highlight_errors();
                    return null;
                }
            }
            if (field.type == 'Float') {
                rv = parseFloat(rv);
                if (rv == NaN) {
                    errors.push([fieldname, 'Invalid input, value not a number']);
                    searchform.highlight_errors();
                    return null;
                }
            }
        }
        return rv;
    };
    
    searchform.clear_errors = function(context) {
        var errors = searchform.control.errors;
        if ((context) && (context.handler)) {
            /* context is event object, redefine as row */
            context = jq(this).parents('td.value').parent('tr');
            var fieldname = jq('td.fieldspec select option:selected', context).val();
            for (var i=0; i < errors.length; i++) {
                var elm = errors[i];
                if (elm[0] == fieldname) errors.splice(errors.indexOf(elm), 1);
            }
        } else {
            context = jq('table.queries');
            searchform.control.errors = [];  // reset all errors
        }
        var e = jq('td.value div.error', context);
        if (e) e.remove();
    };
    
    searchform.add_value_radio = function(row, fieldname, vocabulary, value) {
        var td = jq('td.value', row);
        td.empty();
        for (var i=0; i<vocabulary.length; i++) {
            var term = vocabulary[i];
            var idiv = jq('<div><input type="radio"/></div>').appendTo(td);
            var input = jq('input', idiv);
            var input_name = fieldname + '-' + searchform.datarows().index(row);
            var input_id = input_name + '-' + term;
            input.attr('name', input_name);
            input.attr('id', input_id);
            input.attr('value', term);
            jq('<label>'+term+'</label>').attr('for', input_id).appendTo(idiv);
            input.change(searchform.clear_errors);
        }
        if (typeof value === 'string') {
            jq('input:radio', td).filter('[value='+value+']').attr('checked', true);
        }
    };
    
    searchform.add_value_input = function(row, fieldinfo, value) {
        var td = jq('td.value', row);
        td.empty();
        var fieldname = fieldinfo.name;
        var input_name = fieldname + '-' + searchform.datarows().index(row);
        if (fieldinfo.fieldtype == 'Date') {
            /* date input, use smartdate.js enhanced input */
            jq('<input class="smartdate-widget date-field" type="text" />').appendTo(td).attr('name', input_name);
            smartdate.hookups();
        } else {
            /* default input */
            jq('<input type="text" />').appendTo(td).attr('name', input_name);
        }
        if (typeof value === 'string') {
            jq('input', td).val(value);
        }
        jq('input', td).change(searchform.clear_errors);
    };

    searchform.add_value_selection = function(row, fieldname, vocabulary, value) {
        if (vocabulary.length <= 3) {
            return searchform.add_value_radio(row, fieldname, vocabulary, value);
        }
        var td = jq('td.value', row);
        td.empty();
        var select = jq('<select>').appendTo(td);
        jq('<option>').appendTo(select).val('EMPTY').text('-- SELECT A VALUE --');
        for (var i=0; i<vocabulary.length; i++) {
            var term = vocabulary[i];
            jq('<option>').appendTo(select).val(term).text(term);
        }
        if (typeof value === 'string') {
            select.val(value);
        }
        select.change(searchform.clear_errors);
    };

    searchform.add_value_selections = function(row, fieldname, vocabulary, value) {
        var td = jq('td.value', row);
        td.empty();
        var select = jq('<select multiple="multiple">').appendTo(td);
        for (var i=0; i<vocabulary.length; i++) {
            var term = vocabulary[i];
            jq('<option>').appendTo(select).val(term).text(term);
        }
        console.log(value);
        if ( (Array.isArray(value)) && (typeof value[0] === 'string') ) {
            select.val(value);
        }
        select.change(searchform.clear_errors);
    };
    
    searchform.row_select_comparator = function (row, comparator, value) {
        var v_sel, v_input;
        var field = searchform.row_field(row);
        var fieldname = field.name;
        if (field.fieldtype == 'Choice') {
            vocabulary = field.vocabulary;
            if (comparator == 'Any') {
                searchform.add_value_selections(row, fieldname, vocabulary, value);
            } else {
                searchform.add_value_selection(row, fieldname, vocabulary, value);
            }
            return;
        }
        if (field.value_type == 'Choice') {
            vocabulary = field.vocabulary;
            if ((comparator == 'Any') || (comparator == 'All')) {
                searchform.add_value_selections(row, fieldname, vocabulary, value);
            } else {
                searchform.add_value_selection(row, fieldname, vocabulary, value);
            }
        } else {
            //assume input
            searchform.add_value_input(row, field, value);
        }
        /*
        if (typeof value === 'string') {
            v_sel = jq('td.value select', row);
            if (v_sel.length) {
                console.log('>>>>>' + field.name);
                console.log(value);
                v_sel.val(value);
            } else {
                v_input = jq('td.value input', row);
                if (v_input.length) {
                    v_input.val(value);
                }
            }
        }
        */
    };

    searchform.handle_select_comparator = function (evt) {
        var vocabulary;
        var select = jq(this);
        var selected = jq('option:selected', select);
        var comparator = selected.val();
        var row = select.parents('table.queries tr');
        searchform.row_select_comparator(row, comparator);
    };
    
    searchform.load_comparator_list = function(row, index_types, comparator) {
        var field = searchform.row_field(row);
        var select = jq('<select class="comparator">').appendTo(
            jq('td.compare', row));
        var comparators_url = jq('base').attr('href') +
            '/@@searchapi/comparators';
        comparators_url += '?byindex=' + index_types.join('+') + '&symbols';
        if ((field.value_type == 'Choice') || (field.fieldtype == 'Choice')) {
            comparators_url += '&choice';
        }
        jq('<option>').appendTo(select).attr('value', 'EMPTY').text(
            '-- Choose comparison --');
        jq.ajax({
            url: comparators_url,
            success: function(data) {
                jq.each(data, function (idx, pair) {
                    var name, label;
                    name = pair[0];
                    label = pair[1];
                    jq('<option>').appendTo(select).attr('value', name).text(
                        label);
                    });
                    if (typeof comparator === 'string') {
                        select.val(comparator);
                    }
                }
            });
        select.change(searchform.handle_select_comparator);
    };
    
    searchform.handle_field_selection = function (evt) {
        var dropdown = jq(this),
            selected = jq('option:selected', dropdown),
            fields = searchform.control.fields,
            fieldname = selected.val(),
            field = fields[fieldname],
            row = dropdown.parents('table.queries tr'),
            detail_url;
        detail_url = jq('base').attr('href') + '/@@searchapi/fields/' + fieldname;
        searchform.prep_row_for_field_change(row);
        if (fieldname != 'EMPTY') {
            if (field.useCount() > 1) {
                alert('This field (' + field.title + ') is already in use; please select another.');
                row.remove();
                return;
            }
            searchform.load_comparator_list(row, field.index_types);
        }
    };
    
    searchform.init_fieldspec = function (row, fieldname) {
        var fields, fieldspec, select, title, name;
        fields = searchform.control.fields;
        fieldspec = jq('td.fieldspec', row);
        select = jq('<select class="field-choice" />').appendTo(fieldspec);
        jq('<option>').appendTo(select).attr('value', 'EMPTY').text(
            '-- Choose field --');
        for (name in fields) {
            if (fields.hasOwnProperty(name)) {
                title = fields[name].title;
                jq('<option>').appendTo(select).attr('value', name).text(title);
            }
        }
        if (fieldname) {
            // mark field as selected item
            select.val(fieldname);
        }
        select.change(searchform.handle_field_selection);
    };
    
    searchform.handle_add_click = function (evt) {
        var row = searchform.add_row();
        searchform.init_fieldspec(row);
    };
    
    searchform.rowdata = function(row) {
        var fieldname = searchform.row_field(row).name,
            comparator = jq('td.compare option:checked', row).val(),
            value = searchform.queryvalue(row);
        row = jq(row);
        return new searchform.FieldQuery(fieldname, comparator, value);
    };
    
    searchform.formdata = function() {
        var fieldquery;
        var formdata = new Object();
        formdata.rows = new Array();
        searchform.datarows().each(function(idx, row) {
            fieldquery = searchform.rowdata(row);
            formdata.rows.push(fieldquery.toRecord());
        });
        formdata.operator = searchform.control.operator;
        return formdata;
    };

    searchform.handle_save = function(e) {
        searchform.clear_errors();
        var formdata = searchform.formdata();
        if (searchform.control.errors.length) {
            /* there were some validation errors */
            alert('There were some errors in input; see messages on highlighted fields.');
            return;
        }
        var bundle = JSON.stringify(formdata);
        var payload_form_input = jq('#payload');
        if (payload_form_input.length) {
            payload_form_input.val(bundle);
        }
    };

}

/** searchform types: */
(function () {
    
    /** Field type/ctor */
    searchform.Field = function (name, data) {
        this.name = name;
        for (k in data) {
            if (data.hasOwnProperty(k)) {
                v = data[k];
                if (typeof v != 'function') {
                    this[k] = v;
                }
            }
        }
        return this;
    };
    
    searchform.Field.prototype.rows = function() {
        var fieldname, opt, result = [];
        var rows = searchform.datarows();
        var searchname = this.name;
        jq.each(rows, function (idx, row) {
            opt = jq('td.fieldspec option:selected', row);
            fieldname = opt.val();
            if (fieldname == searchname) {
                result.push(row);
            }
        });
        return jq(result);
    };
    
    searchform.Field.prototype.getRow = function () {
        return jq(this.rows()[0]);
    };
    
    searchform.Field.prototype.useCount = function() {
        return this.rows().length;
    };
    
    /* FieldQuery type */
    searchform.FieldQuery = function (field, comparator, value, row) {
        this.field = field;
        // if field is a name, resolve to Field instance from global state:
        if (typeof field === 'string') {
            this.field = searchform.control.fields[field];
        }
        this.comparator = comparator;
        this.value = value;
        /*  row may be defined jQuery object fronting for one DOM <tr />
            element, or row may be null or empty (temporarily); if
            null or empty, this.initrow() should set it at later time.
         */
        this.row = row;
    };
    
    searchform.FieldQuery.prototype.toRecord = function () {
        // returns simple object with properties only: fieldname, comparator, value
        var r = new Object()
        r.fieldname = this.field.name;
        r.comparator = this.comparator;
        r.value = this.value;
        return r;
    };
    
    searchform.FieldQuery.prototype.initrow = function () {
        /* sync field with row, only if this.row is initially null */
        var new_row, fieldspec, fields, select, title;
        if (!this.isComplete()) {
            // incomplete, do nothing
            if (SFDEBUG) console.log(
                'Warning: FieldQuery.initrow(): query is incomplete.');
            return;
        }
        fields = searchform.control.fields;
        new_row = searchform.add_row();
        searchform.init_fieldspec(new_row, this.field.name);
        searchform.load_comparator_list(
            new_row,
            this.field.index_types,
            this.comparator
            );
        searchform.row_select_comparator(new_row, this.comparator, this.value);
    };
    
    searchform.FieldQuery.prototype.remove = function () {
        /* remove a row, disconnect the query instance from row, field */
        
    };
    
    searchform.FieldQuery.prototype.isComplete = function () {
        // completeness is defined as the 3 primary fields being defined
        return ((!!this.field) && (!!this.comparator) && (this.value != null));
    };
    
    /* form control */
    searchform.FormControl = function () {
        // cross-field operator: AND/OR
        this.operator = 'AND';
        // fields mapping keyed by fieldname identifier
        this.fields = {};
        // global errors state, array of fieldname, msg tuples
        this.errors = []; 
        // state reflecting whether fields are loaded
        this.fields_loaded = false;
        // mutex for async loading state:
        this.fields_loading = false;
        // queue for callback functions, see this.ready()
        this.ready_callbacks = [];
        // cache of ready state for form control:
        this.marked_ready = false;
        return this;
    };
    
    searchform.FormControl.prototype.loadFields = function () {
        var fieldinfo;
        var fields_url = jq('base').attr('href') + '/@@searchapi/fields';
        var self = this;
        if ((!this.fields_loaded) && (!this.fields_loading)) {
            this.fields_loading = true;
            if (SFDEBUG) console.log(
                'FormControl.loadFields(): calling fields API.');
            jq.ajax({
                url: fields_url,
                success: function(data) {
                    for (name in data) {
                        if (data.hasOwnProperty(name)) {
                            fieldinfo = new searchform.Field(name, data[name]);
                            self.fields[name] = fieldinfo;
                        }
                    }
                    self.fields_loaded = true;
                    self.fields_loading = false;
                    if (SFDEBUG) console.log(
                        'FormControl.loadFields(): loaded from API.');
                    self.ready();
                }
            });
        }
    };
    
    searchform.FormControl.prototype.check_ready = function () {
        if (!this.ready_callbacks.length) {
            // nothing to call
            if (SFDEBUG) console.log('check_ready(): no callbacks');
            return false;
        }
        if (this.fields_loaded) {
            if (SFDEBUG) console.log('check_ready(): ready, callbacks waiting');
            return true;
        }
    };
    
    searchform.FormControl.prototype.runqueue = function () {
        /** run all callbacks FIFO in self.ready_callbacks queue */
        if (SFDEBUG) console.log('FormControl.runqueue(): executing callbacks');
        var i = 0,
            cb;
        for ( ; i<this.ready_callbacks.length; i++) {
            cb = this.ready_callbacks.shift();
            if (SFDEBUG) {
                console.log('FormControl.runqueue() calling:');
                console.log(cb);
                }
            cb();
        }
    };
    
    searchform.FormControl.prototype.ready = function (callback) {
        if (callback) {
            if (SFDEBUG) console.log('FormControl.ready() queuing callback');
            this.ready_callbacks.push(callback);
        }
        if (this.check_ready()) {
            if (SFDEBUG) console.log('FormControl.ready(): ready state found');
            this.runqueue();
        }
    };

    searchform.FormControl.prototype.toggle_operator = function () {
        var opbuttons = jq('form.record-queries div.queryop-selection');
        this.operator = jq('input:checked', opbuttons).val();
        searchform.toggle_placeholder();
    };
    
    searchform.FormControl.prototype.loadSaved = function () {
        var saved, i=0, rowdata, q;
        var saved = SF_MOCK; // TODO: replace with real data loading
        if ((saved.operator === 'AND') || (saved.operator === 'OR')) {
            this.operator = saved.operator;
        }
        for ( ; i<saved.rows.length; i++) {
            rowdata = saved.rows[i];
            q = new searchform.FieldQuery(
                rowdata.fieldname,
                rowdata.comparator,
                rowdata.value
                );
            q.initrow();
        }
    };

    
    searchform.FormControl.prototype.initUI = function () {
        var add_query_button, operator_buttons, save_query_button, ctl = this;
        this.loadSaved();
        add_query_button = jq('a.addquery');
        add_query_button.click(searchform.handle_add_click);
        operator_buttons = jq('form.record-queries div.queryop-selection input');
        operator_buttons.change(function() { ctl.toggle_operator() });
        save_query_button = jq('a.savequery');
        save_query_button.click(searchform.handle_save);
    };
    
    // unenforced singleton instance of form control
    searchform.control = new searchform.FormControl();
    
    // prep any initial state from API (async):
    
    searchform.control.loadFields();
    
    // main, on-ready (nested callbacks), assumes DOM must be ready via jQuery:
    
    jq(document).ready(function () {
        // DOM ready callback
        searchform.control.ready(function () {
            // pre-loaded application state ready (main application) callback
            if (SFDEBUG) console.log('FormControl: application state loaded');
            if (SFDEBUG) console.log(searchform.control.fields);
            searchform.control.initUI();
            if (SFDEBUG) console.log('FormControl: user interface loaded');
        });
    });
    
})();


