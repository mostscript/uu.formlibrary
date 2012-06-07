jq = jQuery;

if (!uu) var uu = new Object();  // namespaces
if (!uu.formlibrary) uu.formlibrary = new Object();
if (!uu.formlibrary.searchform) uu.formlibrary.searchform = new Object();

uu.formlibrary.searchform.add_row = function() {
    var table = jq('table.query-filters');
    table.append('<tr><td class="fieldspec"></td><td class="compare"></td><td class="value"></td><td class="rowcontrol"></td></tr>');
    return jq('tr:last', table);  // returns newly appended row
};


uu.formlibrary.searchform.load_comparator_list = function(row, index_types) {
    var select = jq('<select class="comparator">').appendTo(jq('td.compare', row));
    jq('<option>').appendTo(select).attr('value', 'EMPTY').text('-- Choose comparison --');
    var comparators_url = jq('base').attr('href') + '/@@searchapi/comparators';
    comparators_url += '?byindex=' + index_types.join('+') + '&symbols';
    console.log(comparators_url);
    jq.ajax({
        url: comparators_url,
        success: function(data) {   
            console.log(data); //TODO REM
            for (var i=0; i<data.length; i++) {
                var pair = data[i];
                var name = pair[0];
                var label = pair[1];
                jq('<option>').appendTo(select).attr('value', name).text(label);
            }
        }
        });
}

uu.formlibrary.searchform.deselect_field = function(row) {
    jq('td.compare', row).empty();
    jq('td.value', row).empty();
};

uu.formlibrary.searchform.handle_filter_selection = function(e) {
    var dropdown = jq(this);
    var selected_value = jq('option:selected', dropdown).val();
    var row = dropdown.parents('table.query-filters tr');
    uu.formlibrary.searchform.deselect_field(row);
    if (selected_value != 'EMPTY') {
        uu.formlibrary.searchform.deselect_field(row);
        var detail_url = jq('base').attr('href') + '/@@searchapi/filters/' + selected_value;
        jq.ajax({
            url: detail_url,
            success: function(data) {
                console.log(data); //TODO
                var index_types = data.index_types;
                uu.formlibrary.searchform.load_comparator_list(row, index_types);
            }
        });
    }
};

uu.formlibrary.searchform.handle_add_click = function(e) {
    var new_row = uu.formlibrary.searchform.add_row();
    var fieldspec = jq('td.fieldspec', new_row);
    var filters_url = jq('base').attr('href') + '/@@searchapi/filters';
    jq.ajax({
        url: filters_url,
        success: function(data) {
            var fieldnames = new Object();
            for (key in data) {
                var field_info = data[key];
                fieldnames[key] = field_info.title;
            }
            //create widget:
            var select = jq('<select class="field-filter" />').appendTo(fieldspec);
            select.attr('name', 'fieldspec');  // TODO: prefix/suffix
            jq('<option>').appendTo(select).attr('value', 'EMPTY').text('-- Choose field --');
            //populate options:
            for (name in fieldnames) {
                var title = fieldnames[name];
                jq('<option>').appendTo(select).attr('value', name).text(title);
            }
            select.change(uu.formlibrary.searchform.handle_filter_selection);
        }
    });
};

uu.formlibrary.searchform.initbuttons = function() {
    var add_filter_button = jq('a.addfilter');
    add_filter_button.click(uu.formlibrary.searchform.handle_add_click);
};

uu.formlibrary.searchform.init = function() {
    uu.formlibrary.searchform.initbuttons();
};

jq(document).ready(function() {
    uu.formlibrary.searchform.init();
});

