/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

var formsearch = formsearch || {};
formsearch.criteria = formsearch.criteria || {};


(function ($, ns) {
    "use strict";

    // uuid function via http://stackoverflow.com/a/2117523/835961
    ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
    ns.uuid4 = function () {
        return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
            var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
            return v.toString(16);
        });
    };

    // global storage for named snippets
    ns.snippets = {};

    ns.snippets.NOVALUE = String() +
        '<option value="--NOVALUE--">--Select a value--</option>';

    ns.NOVALUE = $(ns.snippets.NOVALUE).attr('value');

    ns.snippets.NEWROW = String() +
        '<tr>' +
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

    ns.snippets.PLACEHOLDER = String() +
        '<tr class="placeholder">' +
        ' <td class="noqueries" colspan="5">' +
        '  <em>There are no queries defined for this filter.</em>' +
        ' </td>' +
        '</tr>';

    // Criteria form HTML: must be modified to change ids
    ns.snippets.CRITERIAFORM = String() +
        '<form id="criteriaform" class="record-queries" action="" method="POST">' +
        '  <table class="queries">' +
        '   <tbody>' +
        '    <tr class="headings">' +
        '      <th class="display-queryop">&nbsp;</th>' +
        '      <th>Field</th><th>Comparison</th>' +
        '      <th>Value</th>' +
        '      <th class="rowcontrol">&nbsp;</th>' +
        '    </tr>' +
        '    <tr class="placeholder">' +
        '      <td class="noqueries" colspan="4">' +
        '        <em>There are no queries defined for this filter.</em>' +
        '      </td>' +
        '    </tr>' +
        '   </tbody>' +
        '  </table>' +
        '  <a class="addquery">' +
        '    <span>' +
        '      <strong>&#x2b;</strong>' +
        '      Add a field query to this filter' +
        '    </span>' +
        '  </a>' +
        '  <div class="queryop-selection">' +
        '    <h5>' +
        '      Select an operation to apply across' +
        '      multiple selected fields.</h5>' +
        '    <input type="radio"' +
        '           name="queryop"' +
        '           value="AND"' +
        '           checked="CHECKED"' +
        '           id="queryop-AND" />' +
        '    <label for="queryop-AND">AND</label>' +
        '    <input type="radio"' +
        '           name="queryop"' +
        '           value="OR"' +
        '           id="queryop-OR"' +
        '           />' +
        '    <label for="queryop-OR">OR</label>' +
        '  </div>' +
        '</form>';

    ns.apiCallCache = {};  // cache url to parsed JSON for GET requests

    //given context element for UI event, get target record-queries form:
    ns.eventTarget = function (context) {
        return $(context).parent('form.record-queries');
    };

    // OrderedMapping: an ordered mapping with string keys, but otherwise
    //                 similar semantics to ECMAScript 6 Map object
    ns.OrderedMapping = function OrderedMapping(iterable) {

        this.init = function (iterable) {
            var self = this;
            this._keys = [];
            this._values = {};
            if (iterable && iterable.length) {
                iterable.forEach(function (pair) {
                    self._values[pair[0]] = pair[1];
                    self._keys.push(pair[0]);
                });
            }

            // event handler callback hooks:
            this.afterDelete = [];
            this.afterAdd = [];
        };

        // Mapping access
        this.get = function (key) {
            return (this.has(key)) ? this._values[key] : undefined;
        };

        // Mapping set and delete
        this.set = function (key, val) {
            this._values[key] = val;
            this._keys.push(key);
            (this.afterAdd || []).forEach(function (callback) {
                callback.apply(self, [key, val]);
            });
        };

        this.delete = function (key) {
            var idx = this._keys.indexOf(key),
                value = this.get(key),
                self = this;
            if (idx < 0) {
                return false;
            }
            this._keys.splice(idx, 1);
            delete this._values[key];
            (this.afterDelete || []).forEach(function (callback) {
                callback.apply(self, [key, value]);
            });
            return true;
        };

        // containment and size:

        this.has = function (key) {
            return (this._keys.indexOf(key) < 0) ? false : true;
        };

        this.size = function () {
            return this._keys.length;
        };

        // mapping enumeration:  keys(), values(), items(), forEach()
        this.keys = function () {
            return this._keys.slice(0);  // return copy
        };

        this.values = function (fn) {
            var i = 0,
                r = [],
                names = this._keys;
            fn = fn || function (value) { return value; };
            for (i = 0; i < names.length; i += 1) {
                r.push(fn(this._values[names[i]]));
            }
            return r;
        };

        this.items = function () {
            return this.values(
                function (value) {
                    return [value.name, value];
                }
            );
        };

        this.forEach = function (callback, thisArg) {
            var self = this;
            this._keys.forEach(function (key, idx, keys) {
                var value = self.get(key);
                callback.apply(
                    thisArg || this,
                    [value, key, self]
                );
            });
        };

        this.init(iterable);
    };

    // criteria form element factory, applies form name, to snippet:
    ns.criteriaFormElement = function (name) {
        var form = $(ns.snippets.CRITERIAFORM),
            queryopInputs = $('div.queryop-selection input', form),
            labels = $('div.queryop-selection label', form);
        form.attr('id', form.attr('id') + '-' + name);
        queryopInputs.each(function (idx) {
            var input = $(this);
            input.attr('id', input.attr('id') + '-' + name);
        });
        labels.each(function (idx) {
            var label = $(this);
            label.attr('for', label.attr('for') + '-' + name);
        });
        return form;
    };

    // Field: Class for object representing a field's metadata:
    ns.Field = function Field(context, name, data) {

        // ctor: (adapted) context is a CriteriaForm object
        this.init = function (context, name, data) {
            var self = this;
            if (!context instanceof ns.CriteriaForm) {
                throw new TypeError('Field context must be a CriteriaForm');
            }
            this.context = context;
            this.name = name;
            Object.keys(data).forEach(function (k) {
                var v = data[k];
                self[k] = (typeof v !== 'function') ? v : undefined;
            });
        };

        // is field Choice or collection of multiple Choice?
        this.isChoice = function () {
            var fieldtype = this.fieldtype,
                valuetype = this.value_type;
            return (fieldtype === 'Choice' || valuetype === 'Choice');
        };

        this.init(context, name, data);
    };

    // FieldQuery: Class for object representing a query of one field, as
    //             well as any table row in the UI for such query.
    ns.FieldQuery = function FieldQuery(context, field, comparator, value) {

        Object.defineProperties(
            this,
            {
                field: {
                    set: function (v) {
                        var self = this,
                            prev = this._field,
                            name,
                            changed = (prev == null || v !== prev);
                        // Check for null equiv string sentinel set by widget:
                        v = (v === ns.NOVALUE) ? null : v;
                        // enforce uniqueness constraint on fieldname relative
                        // to the containing form that manages this query:
                        if (changed && v != null) {
                            name = v.name;
                            if (this.context.fieldnameInUse(name)) {
                                alert('Field already in use in this form: ' + v.title);
                                v = null;
                            }
                        }
                        // reset dependent data:
                        if (v == null) {
                            this.value = null;
                            this.comparator = null;
                        }
                        // set data value:
                        this._field = v;
                        // sync view:
                        this.initFieldWidget();
                        if (v == null) {
                            this.comparator = null;
                        } else if (changed) {
                            this.comparator = null;
                            this.value = null;
                            this.context.comparators.applyComparators(
                                this.field,
                                function (field, data) {
                                    self.initComparatorWidget(data);
                                }
                            );
                        }
                        this.sync();
                    },
                    get: function () {
                        if (this._field === undefined) {
                            return null;
                        }
                        return this._field;
                    },
                    enumerable: true
                },
                comparator: {
                    set: function (v) {
                        var self = this,
                            prev = this._comparator,
                            changed = (prev == null || v !== prev);
                        if (this.field == null) {
                            this._comparator = null;
                            this.blank();
                        }
                        v = (v === ns.NOVALUE) ? null : v;
                        // reset dependent data:
                        if (v == null) {
                            this.value = null;
                        }
                        // set data value:
                        this._comparator = v;
                        if (v === null) {
                            return;
                        }
                        // sync view:
                        this.context.comparators.applyComparators(
                            this.field,
                            function (field, data) {
                                self.initComparatorWidget(data);
                            }
                        );
                        if (changed) {
                            self.value = null;
                        }
                        this.sync();
                    },
                    get: function () {
                        if (this._comparator === undefined) {
                            return null;
                        }
                        return this._comparator;
                    },
                    enumerable: true
                },
                value: {
                    set: function (v) {
                        // set data value
                        this._value = v;
                        // sync view:
                        this.initValueWidget();
                        this.sync();
                    },
                    get: function () {
                        if (this._value === undefined) {
                            return null;
                        }
                        return this._value;
                    },
                    enumerable: true
                },
                id: {
                    get: function () {
                        if (!this._id) {
                            this._id = ns.uuid4();
                        }
                        return this._id;
                    },
                    set: function (v) {
                        // this cannot be user-set
                    }
                },
                rowname: {
                    get: function () {
                        return this.context.name + '-' + this.id;
                    },
                    set: function (v) {
                        // this cannot be user-set
                    }
                }
            }
        );

        this.init = function (context, field, comparator, value) {
            // every FieldQuery gets a unique, random UUID that should be
            // considered stable throughout its life
            //this.id = ns.uuid4();
            if (!context instanceof ns.CriteriaForm) {
                throw new TypeError('FieldQuery context must be CriteriaForm');
            }
            if (!field instanceof ns.Field) {
                if (typeof field === 'string') {
                    field = context.fields[field];  // get by name
                } else {
                    throw new TypeError('Field parameter not Field object.');
                }
            }
            this.context = context;
            // Create the empty row (keyed based on this.id)
            this.initrow();
            // Setting properties for field/comparator/value also populates UI
            // if appropriate (see mutators for properties defined above):
            this.field = field;
            this.comparator = comparator || null;
            this.value = value || null;
        };

        this.isComplete = function () {
            return (
                this.comparator !== null &&
                this.field !== null &&
                this.value !== null
            );
        };

        // keep payload and data in sync with UI/model
        this.sync = function () {
            if (!this.isComplete()) {
                return;
            }
            this.context.syncPayload();
        };

        // when no field is selected, ensure row has empty comparator and
        // value cells:
        this.blank = function () {
            var rowname = this.rowname,
                row = $('#'+rowname, this.context.target),
                compareCell = $('td.compare', row),
                valueCell = $('td.value', row);
            compareCell.empty();
            valueCell.empty();
        };

        this.initFieldWidget = function () {
            var self = this,
                fields = this.context.fields,
                rowname = this.rowname,
                row = $('#'+rowname, this.context.target),
                cell = $('td.fieldspec', row),
                selname = rowname + '-fieldname',
                select = $('<select />');
            select.attr('name', selname);
            // clear any existing content of cell (empty)
            cell.empty();
            // append select to cell
            select.appendTo(cell);
            // no-value sentinel for dropdown:
            $(ns.snippets.NOVALUE).appendTo(select);
            select.val(ns.NOVALUE);
            // options, given params
            fields.items().forEach(function (pair) {
                var fieldname = pair[0],
                    field = pair[1],
                    isSelected = (self.field && self.field.name === fieldname),
                    option = $('<option />')
                        .appendTo(select)
                        .attr('value', fieldname)
                        .text(field.title);
                if (isSelected) {
                    select.val(fieldname);
                }
            });
            // event callback for change of selected field
            select.change(function () {
                var fieldname = select.val(),
                    field = fields.get(fieldname);
                self.field = (field) ? field : null;
            });
        };

        // given comparators to include and selected name/title pair,
        // initialize the dropdown for the row associated with this.
        this.initComparatorWidget = function (comparators) {
            var self = this,
                rowname = this.rowname,
                row = $('#'+rowname, this.context.target),
                cell = $('td.compare', row),
                selname = rowname + '-comparator',
                select = $('<select />'),
                selected = this.comparator;
            select.attr('name', selname);
            // clear any existing content of cell (empty)
            cell.empty();
            // append select to cell
            select.appendTo(cell);
            // no-value sentinel for dropdown:
            $(ns.snippets.NOVALUE).appendTo(select);
            select.val(ns.NOVALUE);
            // options, given params
            comparators.forEach(function (pair) {
                var option = $('<option />').appendTo(select);
                option.attr('value', pair[0]).text(pair[1]);
            });
            if (selected) {
                select.val(selected);
            }
            // event callback for change of selected comparator
            select.change(function () {
                self.comparator = select.val();
            });
        };

        this.initValueWidget = function () {
            var self = this,
                rowname = this.rowname,
                row = $('#'+rowname, this.context.target),
                cell = $('td.value', row),
                field = this.field,
                comparator = this.comparator,
                value = this.value,
                implSelections,
                implSelection,
                implRadio,
                implInput;
            // empty cell:
            cell.empty();
            if (field == null || comparator == null) {
                return;
            }
            // widget-specific implementations
            //  for selections, single-select, radio, input
            implInput = function (cell, field, value) {
                var fieldname = field.name,
                    inputName = self.context.name + '-' + fieldname + '-value',
                    input = $('<input />');
                input.attr('name', inputName);
                input.attr('id', inputName);
                input.val(value);
                cell.append(input);
                input.change(function () {
                    self.value = input.val();
                });
            };
            implRadio = function (cell, field, value) {
                var fieldname = field.name,
                    inputName = self.context.name + '-' + fieldname + '-value',
                    vocab = field.vocabulary;
                vocab.forEach(function (term) {
                    var idiv = $('<div><input type="radio" /></div>'),
                        input = $('input', idiv),
                        termid = inputName + '-' + term;
                    input.attr('name', inputName)
                        .attr('id', termid)
                        .attr('value', term);
                    if (term === self.value) {
                        input.attr('checked', 'CHECKED');
                    }
                    $('<label>'+term+'</label>').attr('for', termid).appendTo(idiv);
                    idiv.appendTo(cell);
                    input.change(function () {
                        self.value = input.val();
                    });
                });
            };
            implSelection = function (cell, field, value) {
                var select = $('<select />'),
                    vocab = field.vocabulary;
                if (vocab.length <= 3) {
                    return implRadio(cell, field, value);
                }
                $('<option>').appendTo(select).val('EMPTY').text('-- SELECT A VALUE --');
                vocab.forEach(function (term) {
                    $('<option>').appendTo(select).val(term).text(term);
                });
                if (typeof value === 'string') {
                    select.val(value);
                }
                select.appendTo(cell);
                select.change(function () {
                    self.value = select.val();
                });
            };
            implSelections = function (cell, field, value) {
                var select = $('<select multiple="multiple">').appendTo(cell),
                    vocab = field.vocabulary;
                vocab.forEach(function (term) {
                    var option = $('<option>');
                    option.appendTo(select).val(term).text(term);
                    if (Array.isArray(value)) {
                        if ($.inArray(term, value) !== -1) {
                            option.attr('selected', 'selected');
                        }
                    }
                });
                select.appendTo(cell);
                select.change(function () {
                    self.value = select.val();
                });
            };
            if (field.fieldtype === 'Choice') {
                if (comparator === 'Any') {
                    implSelections(cell, field, value);
                } else {
                    implSelection(cell, field, value);
                }
                return;
            }
            if (field.value_type === 'Choice') {
                if ((comparator == 'Any') || (comparator == 'All')) {
                    implSelections(cell, field, value);
                } else {
                    implSelection(cell, field, value);
                }
            } else {
                implInput(cell, field, value);
            }
        };

        // initialize bare row (sync with data for widget cells is
        // handled by mutators); rows are keyed by field name, so the
        // this.field must be set
        this.initrow = function () {
            var self = this,
                form = this.context,
                comparators = form.comparators,
                target = form.target,
                table = $('table.queries', target),
                rowname = this.rowname,
                row = $(ns.snippets.NEWROW).appendTo(table),
                comparatorDetail;
            row.attr('id', rowname);
            $('a.removerow', row).click(function (e) {
                var placeholder = $('tr.placeholder', table);
                $(this).parents('tr#' + rowname).remove();
                self.tearDown();
                self.context.removeQuery(self);
                if (self.context.size() === 0 && placeholder.length === 0) {
                    $(ns.snippets.PLACEHOLDER).appendTo(table);
                }
            });
        };

        // return jQuery-wrapped tr element for query:
        this.getRow = function () {
            var target = this.context.target,
                table = $('table.queries', target);
            return $('#' + this.rowname, table);
        };

        // should be called by CriteriaForm before removing:
        this.tearDown = function () {
            this.getRow().remove();
        };

        this.init(context, field, comparator, value);

    };


    // Ordered Mapping of field name to Field
    ns.Fields = function Fields(context, data) {

        this.init = function (context, data) {
            var fieldnames = [],
                pairs = [],
                self = this;
            this.context = context;  // CritieriaForm instance
            // superclass ctor wants Array of k/v pair tuple arrays
            if (!(data instanceof Array) && data) {
                fieldnames = Object.keys(data);
                if (fieldnames.length === 0) {
                    pairs = [];
                } else {
                    fieldnames.forEach(function (name) {
                        pairs.push(
                            [
                                name,
                                new ns.Field(self.context, name, data[name])
                            ]
                        );
                    });
                }
            }
            ns.Fields.prototype.init.call(this, pairs);
        };

        this.init(data);

    };

    ns.Fields.prototype = new ns.OrderedMapping();


    // CriteriaForm: Class for object representing a criteria form; acts as
    //               an ordered mapping of UUID keys to FieldQuery instances
    ns.CriteriaForm = function CriteriaForm(name, title) {

        // Get container for target: outer div holds wrapper divs with forms
        this._container = function (name) {
            var outer = $('div#criteriaforms'),
                containerid = 'criteria-formwrapper-' + name,
                container = $('#'+containerid, outer);
            if (!container.length) {
                container = $('<div class="formwrapper" />').appendTo(outer);
            }
            container.attr('id', containerid);
            return container;
        };

        this._loadFields = function () {
            var fields_url = $('base').attr('href') + '/@@searchapi/fields',
                self = this;
            $.ajax({
                url: fields_url,
                success : function (data) {
                    self.fields.init(self, data);
                    self._fields_loading = false;
                    self._fields_loaded = true;
                    self.comparators = new ns.Comparators(self.fields);
                    self._loadQueryRows(self.payload);
                }
            });
        };

        // given saved data from initial payload, load query rows
        this._loadQueryRows = function (data) {
            var self = this;
            if (!data.rows.length) {
                return;
            }
            data.rows.forEach(function (row) {
                var name = row.fieldname,
                    comparator = row.comparator,
                    value = row.value,
                    field,
                    query;
                if (!self.fields.has(name)) {
                    return;
                }
                field = self.fields.get(name);
                query = new ns.FieldQuery(self, field, comparator, value);
                self.set(query.id, query);
                // query syncs empty payload during construction, so
                // we need to resync it to this form's payload input:
                query.sync();
            });
            // any saved rows imply no placeholder
            if (self.size()) {
                $('tr.placeholder', this.target).remove();
            }
            // load inter-field query operator from payload
            this.operator = data.operator || 'AND';
        };

        // de-dupe checker
        this.fieldnameInUse = function (name) {
            var queryFieldName = function (q) { return (q.field && q.field.name); },
                inUse = this.values().map(queryFieldName);
            return ($.inArray(name, inUse) !== -1);
        };

        this.syncPayload = function () {
            var queryRows = this.values(),
                result = {},
                mkdata = function (query) {
                    if (!query.isComplete()) {
                        return null;
                    }
                    var qdata = {
                        fieldname: (query.field) ? query.field.name : null,
                        comparator: query.comparator,
                        value: query.value
                    };
                    return qdata;
                },
                hasvalue = function (v) { return  (v != null); };
            result.rows = queryRows.map(mkdata).filter(hasvalue);
            result.operator = this.operator;
            this.payload = result;
        };

        this.removeQuery = function (q) {
            var queryId = q.id;
            this.delete(queryId);
            q.tearDown();
            this.syncPayload();
        };

        // Make a target, if needed:
        this._mktarget = function (container, name, title) {
            var form = ns.criteriaFormElement(name);
            container = container || this._container(name);
            $('<h3 />').text(title).appendTo(container);
            form.appendTo(container);
            return form;
        };

        // Given a name, get the target <form> element, wrapped in jQuery obj
        this._target = function (name, title) {
            var container = this._container(name),
                target = $('form.record-queries', container);
            if (!target.length) {
                target = this._mktarget(container, name, title);
            }
            return target;
        };

        // get or create-and-get payload input
        this._payload = function () {
            var name = this.name,
                inputname = 'payload-' + name,
                payloadForm = $('form#payloads'),
                container = $('div.payload-container', payloadForm),
                input = $('input#'+inputname, container);
            if (!input.length) {
                // no payload input, make one (container should exist)
                input = $('<input type="hidden" />')
                    .attr('name', inputname)
                    .attr('id', inputname)
                    .appendTo(container);
            }
            return input;
        };

        // after events like add/remove rows, show the query operator
        // selection radio widget when there are more than two rows in
        // a critieria form
        this.syncQueryOperatorSelector = function () {
            var opdiv = $('div.queryop-selection', this.target);
            if (this.size() >= 2) {
                opdiv.show();
            } else {
                opdiv.hide();
            }
        };

        // add a new query row
        this.newquery = function () {
            var q = new ns.FieldQuery(this),
                opdiv = $('div.queryop-selection', this.target),
                opinputs = $('input', opdiv);
            this.set(q.id, q);
            opinputs.change();
            $('tr.placeholder', this.target).remove();
        };

        // UI event handler hookups for form-scoped elements
        this.initUIEvents = function () {
            var self = this,
                addbtn = $('a.addquery', this.target),
                opdiv = $('div.queryop-selection', this.target),
                opinputs = $('input', opdiv);
            addbtn.click(function () {
                self.newquery();
            });
            opinputs.change(function () {
                var showOp = (self.size() >= 2),
                    table = $('table.queries', self.target),
                    showrows = $('tr', table).not('.headings').slice(1),
                    queryOpCells = $('td.display-queryop', showrows);
                if (showOp) {
                    queryOpCells.text(self.operator);
                } else {
                    queryOpCells.text(' ');
                }
                self.syncPayload();
            });
        };

        this.init = function (name, title) {
            var self = this,
                _toggleQueryOp = function (k, v) {
                    self.syncQueryOperatorSelector();
                };
            title = title || name;
            this.name = name;
            this.target = this._target(name, title);
            this.fields = new ns.Fields();
            this._fields_loaded = false;
            this._fields_loading = false;
            Object.defineProperties(this, {
                title: {
                    set: function (value) {
                        $('h3', this._container(self.name)).text(value);
                    },
                    get: function () {
                        $('h3', this._container(self.name)).text();
                    },
                    enumerable: true
                },
                operator: {
                    set: function (value) {
                        var target = self.target,
                            opbuttons = $('div.queryop-selection', target),
                            orbtn = $('input[value="OR"]', opbuttons),
                            andbtn = $('input[value="AND"]', opbuttons);
                        if (value !== 'AND' && value !== 'OR') {
                            return;
                        }
                        if (value === 'OR') {
                            orbtn.attr('checked', 'CHECKED');
                        } else {
                            andbtn.attr('checked', 'CHECKED');
                        }
                    },
                    get: function () {
                        var target = self.target,
                            opbuttons = $('div.queryop-selection', target);
                        return $('input:checked', opbuttons).val() || 'AND';
                    },
                    enumerable: true
                },
                payload: {
                    set: function (value) {
                        var payload = self._payload();
                        if (!(value instanceof String)) {
                            value = JSON.stringify(value);
                        }
                        payload.val(value);
                    },
                    get: function () {
                        var payload = self._payload(),
                            v = payload.val();
                        if (!v) {
                            return [];
                        }
                        return JSON.parse(v);
                    },
                    enumerable: true
                }
            });
            this.comparators = null;  // set async after load of fields
            this._loadFields();
            ns.CriteriaForm.prototype.init.call(this, []);
            this.initUIEvents();
            this.afterAdd = [_toggleQueryOp];
            this.afterDelete = [_toggleQueryOp];
        };

        this.tearDown = function () {
            this._container(this.name).remove();
        };

        this.init(name, title);
    };

    ns.CriteriaForm.prototype = new ns.OrderedMapping();


    // Comparators: object fronting for access to comparators
    // ajax/json requests
    ns.Comparators = function Comparators(fields) {

        this.init = function (fields) {
            this.fields = fields;
            this._cache = {};
        };

        this._field = function (spec) {
            return (typeof spec === 'string') ? this.fields.get(spec) : spec;
        };

        // async get and apply callback to fetched comparators
        this.applyComparators = function (field, callback) {
            var url = $('base').attr('href') + '/@@searchapi/comparators',
                self = this;
            field = this._field(field);
            if ($.inArray(field.name, Object.keys(this._cache)) !== -1) {
                callback(field, this._cache[field.name]);
                return;
            }
            if ($.inArray(url, Object.keys(ns.apiCallCache)) !== -1) {
                callback(field, ns.apiCallCache[url]);
            }
            url += '?byindex=' + field.index_types.join('+') + '&symbols';
            if (field.isChoice()) {
                url += '&choice';
            }
            $.ajax({
                url: url,
                async: true,
                success: function (data) {
                    self._cache[field.name] = data;
                    ns.apiCallCache[url] = data;
                    callback(field, data);
                }
            });
        };

        this.init(fields);
    };

    // CriteriaForms:   Class for FIFO collection of CriteriaForms;
    //                  singleton utility and houses global functions,
    //                  which may adapt / act on CriteriaForm instances.
    ns.CriteriaForms = function CriteriaForms() {

        this.init = function () {
            var manager = $('#filter-manager'),
                elem = '<div id="criteriaforms" />';
            this.wrapper = $('div#criteriaforms');
            if (!manager.length) {
                // no content-core div, fall back to first div in #content
                manager = $('#content div');
            }
            if (!this.wrapper.length) {
                this.wrapper = $(elem).appendTo(manager);
            }
            ns.CriteriaForms.prototype.init.apply(this, []);

            // CriteriaForms container event handler callback hooks:
            this.afterDelete = [this._afterDelete];
        };

        this._afterDelete = function (key, value) {
            value.tearDown();
        };

        this.create = function (name, title) {
            return new ns.CriteriaForm(name, title);
        };

        this.add = function (form) {
            var name;
            if (!form instanceof ns.CriteriaForm) {
                throw new TypeError('Item not CriteriaForm; cannot add.');
            }
            if (!form.name) {
                throw new Error('Unnamed forms not allowed.');
            }
            name = form.name;
            this.set(name, form);
        };

        this.has = function (key) {
            var name = (key instanceof ns.CriteriaForm) ? key.name : key;
            return ns.CriteriaForms.prototype.has.apply(this, [name]);
        };

        this.init();
    };
    ns.CriteriaForms.prototype = new ns.OrderedMapping();

    // discover record filters for measure from template;
    //  --> return name/title pairs
    ns.discoverFilters = function () {
        var linksel = 'link[rel="recordfilter"]',
            filterLinks = $(linksel),
            getTitle = function (l) { return $(l).attr('title'); },
            getName = function (l) { return $(l).attr('href'); },
            result = [];
        filterLinks.each(function () {
            result.push([getName(this), getTitle(this)]);
        });
        return result;
    };

    // main application invocation:
    $(document).ready(function () {
        ns.forms = new ns.CriteriaForms();
        ns.discoverFilters().forEach(function (pair) {
            ns.forms.add(ns.forms.create(pair[0], pair[1]));
        });
    });

}(jQuery, formsearch.criteria));

