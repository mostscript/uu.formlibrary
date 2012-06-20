jq = jQuery;

if (!uu) var uu = new Object();  // namespaces
if (!uu.formlibrary) uu.formlibrary = new Object();
if (!uu.formlibrary.searchform) uu.formlibrary.searchform = new Object();

uu.formlibrary.searchform.add_row = function() {
    var table = jq('table.queries');
    var row = jq('<tr><td class="display-queryop">&nbsp;</td><td class="fieldspec"></td><td class="compare"></td><td class="value"></td><td class="rowcontrol"><a class="removerow" title="Remove query row"><img src="./delete_icon.png" alt="delete"/></a></td></tr>').appendTo(table);
    jq('a.removerow', row).click(function(e) {
        jq(this).parents('table.queries tr').remove();
        uu.formlibrary.searchform.toggle_placeholder();
    });
    jq('table.queries tr:nth-child(2n)').addClass('even');  /* cross-browser zebra striping marker */
    return row;
};


uu.formlibrary.searchform.rowno = function(row) {
    var table = jq(row).parents('table.queries');
    var rows = jq('tr').not('tr.headings');
    return rows.index(row);
}

uu.formlibrary.searchform.add_value_radio = function(row, fieldname, vocabulary) {
    var td = jq('td.value', row);
    td.empty();
    for (var i=0; i<vocabulary.length; i++) {
        var term = vocabulary[i];
        var idiv = jq('<div><input type="radio"/></div>').appendTo(td);
        var input = jq('input', idiv);
        var input_name = fieldname + '-' + uu.formlibrary.searchform.rowno(row);
        var input_id = input_name + '-' + term;
        input.attr('name', input_name);
        input.attr('id', input_id);
        input.attr('value', term);
        jq('<label>'+term+'</label>').attr('for', input_id).appendTo(idiv);
    }
}

uu.formlibrary.searchform.add_value_input = function(row, fieldinfo) {
    var td = jq('td.value', row);
    td.empty();
    var fieldname = fieldinfo.fieldname;
    var input_name = fieldname + '-' + uu.formlibrary.searchform.rowno(row);
    if (fieldinfo.fieldtype == 'Date') {
        /* date input, use smartdate.js enhanced input */
        jq('<input class="smartdate-widget date-field" type="text" />').appendTo(td).attr('name', input_name);
        smartdate.hookups();
    } else {
        /* default input */
        jq('<input type="text" />').appendTo(td).attr('name', input_name);
    }
}

uu.formlibrary.searchform.add_value_selection = function(row, fieldname, vocabulary) {
    if (vocabulary.length <= 3) {
        return uu.formlibrary.searchform.add_value_radio(row, fieldname, vocabulary);
    }
    var td = jq('td.value', row);
    td.empty();
    var select = jq('<select>').appendTo(td);
    jq('<option>').appendTo(select).val('EMPTY').text('-- SELECT A VALUE --');
    for (var i=0; i<vocabulary.length; i++) {
        var term = vocabulary[i];
        jq('<option>').appendTo(select).val(term).text(term);
    }
};

uu.formlibrary.searchform.add_value_selections = function(row, fieldname, vocabulary) {
    var td = jq('td.value', row);
    td.empty();
    var select = jq('<select multiple="multiple">').appendTo(td);
    for (var i=0; i<vocabulary.length; i++) {
        var term = vocabulary[i];
        jq('<option>').appendTo(select).val(term).text(term);
    }
};

uu.formlibrary.searchform.handle_select_comparator = function(e) {
    var vocabulary;
    var select = jq(this);
    var selected = jq('option:selected', select);
    var value = selected.val();
    var row = select.parents('table.queries tr');
    var fieldname = jq('td.fieldspec select option:selected', row).val();
    var fieldinfo = uu.formlibrary.searchform.query_data[fieldname];
    if (fieldinfo.fieldtype == 'Choice') {
        vocabulary = fieldinfo.vocabulary;
        if (value == 'Any') {
            uu.formlibrary.searchform.add_value_selections(row, fieldname, vocabulary);
        } else {
            uu.formlibrary.searchform.add_value_selection(row, fieldname, vocabulary);
        }
        return;
    }
    if (fieldinfo.value_type == 'Choice') {
        vocabulary = fieldinfo.vocabulary;
        if ((value == 'Any') || (value == 'All')) {
            uu.formlibrary.searchform.add_value_selections(row, fieldname, vocabulary);
        } else {
            uu.formlibrary.searchform.add_value_selection(row, fieldname, vocabulary);
        }
    } else {
        //assume input
        uu.formlibrary.searchform.add_value_input(row, fieldinfo);
    }
};

uu.formlibrary.searchform.load_comparator_list = function(row, index_types) {
    var fieldname = jq('td.fieldspec select option:selected', row).val();
    var fieldinfo = uu.formlibrary.searchform.query_data[fieldname];
    var select = jq('<select class="comparator">').appendTo(jq('td.compare', row));
    jq('<option>').appendTo(select).attr('value', 'EMPTY').text('-- Choose comparison --');
    var comparators_url = jq('base').attr('href') + '/@@searchapi/comparators';
    comparators_url += '?byindex=' + index_types.join('+') + '&symbols';
    if ((fieldinfo.value_type == 'Choice') || (fieldinfo.fieldtype == 'Choice')) {
        comparators_url += '&choice';
    }
    jq.ajax({
        url: comparators_url,
        success: function(data) {   
            for (var i=0; i<data.length; i++) {
                var pair = data[i];
                var name = pair[0];
                var label = pair[1];
                jq('<option>').appendTo(select).attr('value', name).text(label);
            }
        }
        });
    select.change(uu.formlibrary.searchform.handle_select_comparator);
};

uu.formlibrary.searchform.deselect_field = function(row) {
    jq('td.compare', row).empty();
    jq('td.value', row).empty();
};


uu.formlibrary.searchform.field_in_use = function(fieldname) {
    var table = jq('table.queries');
    var rows = jq('tr', table.queries).not('tr.headings');
    if (rows.length > 0) {
        match = jq('td.fieldspec select option:selected', rows);
        var use_count = 0;
        for (var i=0; i<match.length; i++) {
            var opt = jq(match[i]);
            if (opt.val() == fieldname) {
                use_count += 1;
            }
        }
        if (use_count > 1) {
            return true;
        }
    }
    return false;
};

uu.formlibrary.searchform.handle_field_selection = function(e) {
    var dropdown = jq(this);
    var selected = jq('option:selected', dropdown);
    var selected_value = selected.val(); 
    var row = dropdown.parents('table.queries tr');
    uu.formlibrary.searchform.deselect_field(row);
    if (selected_value != 'EMPTY') {
        uu.formlibrary.searchform.deselect_field(row);
        if (uu.formlibrary.searchform.field_in_use(selected_value)) {
            alert('This field (' + selected.text() + ') is already in use; please select another.');
            row.remove();
            return;
        }
        var detail_url = jq('base').attr('href') + '/@@searchapi/fields/' + selected_value;
        jq.ajax({
            url: detail_url,
            success: function(data) {
                var index_types = data.index_types;
                uu.formlibrary.searchform.load_comparator_list(row, index_types);
            }
        });
    }
};


uu.formlibrary.searchform.handle_query_data = function(fieldspec, data) {
    var fieldnames = new Object();
    for (key in data) {
        var field_info = data[key];
        fieldnames[key] = field_info.title;
    }
    //create widget:
    var select = jq('<select class="field-choice" />').appendTo(fieldspec);
    select.attr('name', 'fieldspec');  // TODO: prefix/suffix
    jq('<option>').appendTo(select).attr('value', 'EMPTY').text('-- Choose field --');
    //populate options:
    for (name in fieldnames) {
        var title = fieldnames[name];
        jq('<option>').appendTo(select).attr('value', name).text(title);
    }
    select.change(uu.formlibrary.searchform.handle_field_selection);
};

uu.formlibrary.searchform.toggle_placeholder = function() {
    var placeholder = jq('table.queries td.noqueries').parent('tr');
    var rowcount = jq('table.queries td').parent('tr').length - placeholder.length;
    /* if >2 rows, show operator radio buttons below table */
    var opbuttons = jq('form.record-queries div.queryop-selection');
    var v_rows = jq('table.queries tr').not('.headings');
    if (rowcount >= 2) {
        opbuttons.show();
        var operator = jq('input:checked').val();
        jq('td.display-queryop', v_rows).not(':first').text('-- ' + operator + ' --');
    } else {
        opbuttons.hide();
        jq('td.display-queryop', v_rows).html('&nbsp;');
    }
    /* placeholder text: */
    if ((rowcount == 0) && (placeholder.length == 0)) {
        /* no placeholder, but no rows, there should be a placeholder;
           placeholder uses content, not CSS toggle to make rowcount
           sane
         */
        var html = '<tr><td class="noqueries" colspan="5"><em>There are no queries defined for this filter.</em><!--placeholder--></td></tr>';
        jq(html).appendTo(jq('table.queries'));
    } else if ((rowcount == 0) && (placeholder.length == 1)) {
        return; // no rows, placeholder already in place
    } else if (placeholder.length > 0) {
        /* positive rowcount, should never have placeholder; remove if found */
        placeholder.remove(); 
    }
}

uu.formlibrary.searchform.handle_add_click = function(e) {
    var new_row = uu.formlibrary.searchform.add_row();
    var fieldspec = jq('td.fieldspec', new_row);
    var fields_url = jq('base').attr('href') + '/@@searchapi/fields';
    if (!uu.formlibrary.searchform.query_data) {
        jq.ajax({
            url: fields_url,
            success: function(data) {
                uu.formlibrary.searchform.toggle_placeholder();
                uu.formlibrary.searchform.query_data = data;  // save/cache state for later use
                uu.formlibrary.searchform.handle_query_data(fieldspec, data);
            }
        });
    } else {
        uu.formlibrary.searchform.toggle_placeholder();
        uu.formlibrary.searchform.handle_query_data(fieldspec, uu.formlibrary.searchform.query_data);
    }
};

uu.formlibrary.searchform.initbuttons = function() {
    var add_query_button = jq('a.addquery');
    add_query_button.click(uu.formlibrary.searchform.handle_add_click);
    var operator_buttons = jq('form.record-queries div.queryop-selection input');
    operator_buttons.change(uu.formlibrary.searchform.toggle_placeholder);
};

uu.formlibrary.searchform.init = function() {
    uu.formlibrary.searchform.initbuttons();
};

jq(document).ready(function() {
    uu.formlibrary.searchform.init();
});

