/** 
 * criteria.js: criteria editor / support advanced and basic criteria query
 *              editing.
 */

/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true,
         undef:true
 */
/*global jQuery, console, QUnit, COREMODELNS, window, alert */


// org namespace:
var uu = uu || {};


// queryschema module:
uu.queryschema = (function ($, ns, uu, core, global) {

    var c = {};

    ns.schemaURL = function () {
        return ($('base').attr('href') || '') + '/@@searchapi/fields';
    };

    /**
     * cAjax(): cached ajax GET requests
     */
    ns.cAjax = function (options) {
        var url = options.url,
            callback = options.success,
            wrapper = function (data) {
                callback.call(this, data);
                ns.apiCallCache[url] = data;
            },
            context = options.context || options,
            cachedResult;
        if (!url || options.type === 'POST') return;  // uncachable
        cachedResult = ns.apiCallCache[url];
        if (cachedResult) {
            return callback.call(context, cachedResult);
        }
        options.success = wrapper;
        $.ajax(options);
    };

    // module-scoped data:
    ns.apiCallCache = {};  // cache url to parsed JSON for GET requests

    // TermInfo: vocabulary term for choices of Comparator, Value
    ns.TermInfo = function (value, label, prefix) {

        this.init = function (value, label, prefix) {
            this.value = value || null;
            this.label = label || this.value;
            this.prefix = prefix || null;  // label prefix
        };

        this.display_label = function () {
            if (typeof this.prefix === 'string') {
                return this.prefix + ' ' + this.label;
            }
            return this.label;
        };

        this.init(value, label, prefix);
    };

    // Field: object representing metadata for a single schema field:
    ns.Field = function Field(name, data) {

        this.init = function (name, data) {
            this.name = name;
            Object.keys(data).forEach(function (k) {
                var v = data[k],
                    name = (k === 'vocabulary') ? '_vocabulary' : k;
                this[name] = (typeof v !== 'function') ? v : undefined;
            }, this);
        };

        // is field a Choice or collection of multiple Choice?
        this.isChoice = function () {
            return (
                this.fieldtype === 'Choice' ||
                this.value_type === 'Choice' ||
                this.fieldtype === 'Bool'
            );
        };

        this.vocabulary = function () {
            if (!this.isChoice()) {
                return null;
            }
            return this._vocabulary.map(function (v) {
                return new ns.TermInfo(v);
            });
        };

        this.init(name, data);
    };

    /**
     * Schema: mapping of field names to Field objects, may preserve order
     */
    ns.Schema = function Schema(data) {

        this.init = function (data) {
            var pairs = data;
            // superclass ctor wants Array of k/v pair tuple arrays
            if (!(data instanceof Array) && data) {
                pairs = Object.keys(data).map(function (name) {
                    return [name, new ns.Field(name, data[name])];
                }, this);
            }
            ns.Schema.prototype.init.call(this, {iterable: pairs});
        };

        this.init(data);
    };
    core.klass.subclasses(ns.Schema, core.Container);

    ns.comparators = c;

    c.ALL = new ns.TermInfo('All', 'contains all of','\u2286');
    c.ANY = new ns.TermInfo('Any', 'includes any of','*');
    c.CONTAINS = new ns.TermInfo('Contains', 'contains','\u2208');
    c.DOESNOTCONTAIN = new ns.TermInfo(
        'DoesNotContain',
        'does not contain',
       '\u2209'
        );
    c.EQ = new ns.TermInfo('Eq', 'is equal to','=');
    c.GE = new ns.TermInfo('Ge', 'is greater than or equal to','\u2264');
    c.GT = new ns.TermInfo('Gt', 'is greater than','>');
    c.INRANGE = new ns.TermInfo('InRange', 'is between','(\u2026)');
    c.LE = new ns.TermInfo('Le', 'is less than or equal to','\u2265');
    c.LT = new ns.TermInfo('Lt', 'is less than','<');
    c.NOTEQ = new ns.TermInfo('NotEq', 'is not','\u2260');
    c.NOTINRANGE = new ns.TermInfo('NotInRange', 'is not between','\u2209');

    ns.COMPARATORS_BY_INDEX = {
        'field': [
            c.ANY, c.EQ, c.GE, c.GT, c.INRANGE, c.LE, c.LT, c.NOTEQ,
            c.NOTINRANGE
        ],
        'text': [c.CONTAINS, c.DOESNOTCONTAIN],
        'keyword': [c.ANY, c.ALL, c.DOESNOTCONTAIN]
        };

    ns.CHOICE_OMIT = [c.LT, c.LE, c.GT, c.GE, c.INRANGE, c.NOTINRANGE];

    /**
     * Comparators: global adapts schema, can apply comparator choices
     *              to a callback for a field via applyComparators.
     */
    ns.Comparators = function Comparators(schema) {

        this.init = function (schema) {
            this.schema = schema;
            this._cache = {};
        };

        this._field = function (spec) {
            return (typeof spec === 'string') ? this.schema.get(spec) : spec;
        };

        this.vocabulary = function (spec) {
            var field = this._field(spec),
                choice = field.isChoice(),
                omit = (choice) ? ns.CHOICE_OMIT : [],
                idxTypes = field.index_types || ['field'],
                comparators = [].concat.apply(
                    [],
                    idxTypes.map(
                        function (idxtype) {
                            return ns.COMPARATORS_BY_INDEX[idxtype];
                        }
                    )
                ).filter(
                    function (info) {
                        return (omit.indexOf(info) === -1);
                    }
                );
            return comparators;
        };

        this.init(schema);
    };
    return ns;

}(jQuery, uu.queryschema || {}, uu, window[COREMODELNS], window));


// queryeditor module:
uu.queryeditor = (function ($, ns, uu, core, global) {
    "use strict";

    var cAjax = uu.queryschema.cAjax,
        schemaURL = uu.queryschema.schemaURL;

    /**
     * schema acquisition functions, used for property descriptor on
     * the containment chain of objects, such that contained FieldQuery,
     * RecordFilter, and FilterGroup items could get the schema from
     * the containing ComposedQuery object:
     */

    function acquire_schema(context) {
        var parent = context.context;
        if (parent) {
            return context._schema || parent.schema;
        }
        return context._schema;  // end of chain, may be undefined or null
    }

    function acquire_comparators(context) {
        var parent = context.context;
        if (parent) {
            return context._comparators || parent.comparators;
        }
        return context._comparators;  // end of chain, may be undefined or null
    }

    // makes acquisition possible on schema, comparators properties:
    function initSchemaContext(context) {
        Object.defineProperties(
            context,
            {
                'schema': {
                    get: function () {
                        return acquire_schema(this);
                    }
                },
                'comparators': {
                    get: function () {
                        return acquire_comparators(this);
                    }
                }
            }
        );
    }

    // invariant for component construction options:
    function validateOptions(options) {
        // no empty options, given other constraints:
        if (!options) {
            throw new Error('no provided construction options');
        }
        // EVERY component must be constructed with either a schema or
        // a context that can provide the schema.
        if (!(options.schema instanceof uu.queryschema.Schema)) {
            if (!options.context) {
                throw new Error(
                    'Construction must be provided either schema or context.'
                    );
            }
        }
    }

    // unloaded singleton default values:
    ns.schema = null;           // will be ns.Schema instance
    ns.comparators = null;      // later ns.Comparators instance

    // named snippets of HTML for use in creation:
    ns.snippets = {};

    // RecordFilter (inner) HTML: must be modified to change ids
    ns.snippets.RECORDFILTER = String() +
        '  <table class="queries">' +
        '   <tbody>' +
        '    <tr class="headings">' +
        '      <th class="display-queryop">' +
        '        <a class="addquery"' +
        '           title="Add a field query to this filter">' +
        '          <span>'+
        '            <strong>&#x2b;</strong>' +
        '          </span>'+
        '        </a>' +
        '      </th>' +
        '      <th>Field</th><th>Comparison</th>' +
        '      <th>Value</th>' +
        '      <th class="rowcontrol">' +
        '  <a class="removefilter" title="Remove this filter">' +
        '   <img src="./delete_icon.png" alt="delete"/>' +
        '  </a>' +
        '       &nbsp;</th>' +
        '    </tr>' +
        '    <tr class="placeholder">' +
        '      <td class="noqueries" colspan="5">' +
        '        <em>There are no queries defined for this filter.</em>' +
        '      </td>' +
        '    </tr>' +
        '   </tbody>' +
        '  </table>' +
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
        '  </div>';

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

    ns.snippets.GROUPCONTROL = String() +
        '<div class="groupcontrol">' +
        '  <a class="addfilter" title="Add a filter to this group">' +
        '    <span><strong>&#x21f2;</strong></span> Add filter' +
        '  </a>' +
        '  <div class="groupop-selection">' +
        '    <em class="grouplabel">Operator to apply across filters:</em>' +
        '    <input type="radio"' +
        '           name="groupop"' +
        '           value="union"' +
        '           id="groupop-union"' +
        '           checked="CHECKED"' +
        '           />' +
        '    <label for="groupop-OR">OR (union)</label>' +
        '    <input type="radio"' +
        '           name="groupop"' +
        '           value="intersection"' +
        '           id="groupop-intersection" />' +
        '    <label for="groupop-intersection">AND (intersection)</label>' +
        '    <input type="radio"' +
        '           name="groupop"' +
        '           value="difference"' +
        '           id="groupop-intersection" />' +
        '    <label for="groupop-intersection">MINUS (complement)</label>' +
        '  </div>' +
        '</div>';

    ns.snippets.NOVALUE = String() +
        '<option value="--NOVALUE--">--Select a value--</option>';

    ns.NOVALUE = $(ns.snippets.NOVALUE).attr('value');

    ns.warnfn = null;

    // warn function, can be overridden if needed:
    ns.warn = function warn(message) {
        var fn = ns.warnfn || alert;
        fn(message);
    };

    /**
     * FieldQuery:  item contains info for one basic query of a single
     *              field.
     */
    ns.FieldQuery = function FieldQuery(options) {

        initSchemaContext(this);

        // normalize and validate field, return normalized value
        this.validateField = function (v) {
            var existing = this._field;
            if (v === null) {
                return v;
            }
            if (typeof v === 'string') {
                v = this.schema.get(v);  // fieldname -> field
            }
            if (!(v instanceof uu.queryschema.Field)) {
                throw new TypeError('Invalid field type');
            }
            if (this.schema.keys().indexOf(v.name) === -1) {
                throw new Error('improper field, not in schema');
            }
            if (this.context && this.context.fieldnameInUse(v.name)) {
                if (!existing || (existing && existing.name !== v.name)) {
                    // fieldname is in use, but not by this FieldQuery:
                    // treat as duplicate/conflict, warn and return existing:
                    ns.warn('Field already in use in this filter: ' + v.title);
                    return this._field;
                }
            }
            return v;
        };

        Object.defineProperties(
            this,
            {
                field: {
                    get: function () {
                        return this._field;
                    },
                    set: function (v) {
                        v = this.validateField(v);  // validate, normalize
                        this._field = v;
                        this.sync();
                    },
                    enumerable: true
                },
                comparator: {
                    get: function () {
                        return this._comparator;
                    },
                    set: function (v) {
                        this._comparator = v;
                        this.sync();
                    },
                    enumerable: true
                },
                value: {
                    get: function () {
                        return this._value;
                    },
                    set: function (v) {
                        this._value = v;
                        this.sync();
                    },
                    enumerable: true
                },
            }
        );

        this._mktarget = function () {
            var self = this,
                target = $(ns.snippets.NEWROW),
                context = this.context || {},
                container = $(context.target);
            if (container.length) {
                target.appendTo($('table.queries tbody', container));
                this.target = target;
                target.attr('id', this.targetId);
                $('a.removerow', target).unbind().click(function () {
                    target.remove();
                    context.delete(self.id);
                    context.sync(self);
                });
                this.sync();
            }
        };

        this.init = function (options) {
            validateOptions(options);
            ns.FieldQuery.prototype.init.apply(this, [options]);
            this._field = options.field || null;
            this._comparator = options.comparator || null;
            this._value = options.value || null;
            this._schema = options.schema || undefined;
            this._comparators = options.comparators || undefined;
            if (this._field && this.schema) {
                if (!this.schema.has(this._field.name)) {
                    throw new Error('Field in ctor not in bound schema');
                }
            }
            if (!options.target && options.context) {
                this._mktarget();
            }
        };

        this.normalizedValue = function () {
            var complete = this.completionState(),
                field = this.field,
                value = this.value;
            if (!complete) {
                return null;
            }
            if (field.fieldtype === 'Int' && value != null) {
                return parseInt(value, 10);
            }
            if (field.fieldtype === 'Float' && value != null) {
                return parseFloat(value);
            }
            return this.value;
        };

        this.toJSON = function () {
            var complete = this.completionState(),
                payload = {};
            if (!complete) {
                return {};
            }
            payload.field = this.field.name;
            payload.comparator = this.comparator;
            payload.value = this.normalizedValue(this.value);
            return payload;
        };

        this.completionState = function () {
            var field = this._field,
                comparator = this._comparator,
                value = this._value;
            if (!field && !comparator && !value) {
                return null;   // EMPTY, nothing defined yet
            }
            if (field && comparator && value) {
                if (value instanceof Array && value.length === 0) {
                    return false;  // empty selection is incomplete
                }
                return true;
            }
            return false;  // incomplete, but not empty
        };

        // value widget type determiner:
        this.inputType = function () {
            var field = this.field,
                comparator = this.comparator,
                choice = (!!field) ? field.isChoice() : false,
                chooseOnlyOne = (['Any', 'All'].indexOf(comparator) === -1),
                select;
            if (!field || !comparator) {
                return null;
            }
            if (choice) {
                select = (field.vocabulary().length <= 3) ? 'radio' : 'select';
                return (chooseOnlyOne) ? select : 'multi';
            }
            return 'input';  // fallback/default
        };

        // UI/view sync:

        this.initFieldWidget = function () {
            var self = this,
                schema = this.schema,
                row = this.target,
                cell = $('td.fieldspec', row),
                selname = this.targetId + '-fieldname',
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
            schema.forEach(function (field) {
                var fieldname = field.name,
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
            select.unbind().change(function () {
                var fieldname = select.val(),
                    field = schema.get(fieldname),
                    prev = (self.field) ? self.field.name : null,
                    changed = (fieldname !== prev);
                self.field = (field) ? field : null;
                if (changed) {
                    // reset comparator and value on field change
                    self.comparator = null;
                    self.value = null;
                }
            });
        };

        // given comparators to include and selected name/title pair,
        // initialize the dropdown for the row associated with this.
        this.initComparatorWidget = function (vocab) {
            var self = this,
                row = this.target,
                cell = $('td.compare', row),
                selname = this.targetId + '-comparator',
                select = $('<select />'),
                selected = this.comparator;
            select.attr('name', selname);
            // clear any existing content of cell (empty)
            cell.empty();
            if (!vocab) {
                return;  // reset field to null
            }
            // append select to cell
            select.appendTo(cell);
            // no-value sentinel for dropdown:
            $(ns.snippets.NOVALUE).appendTo(select);
            select.val(ns.NOVALUE);
            // options, given params
            vocab.forEach(function (term) {
                var option = $('<option />').appendTo(select),
                    label = term.display_label();
                option.attr('value', term.value).text(label);
            });
            if (selected) {
                select.val(selected);
            }
            // event callback for change of selected comparator
            select.unbind().change(function () {
                var v = select.val();
                v = (v === ns.NOVALUE) ? null : v;
                self.value = null;  // reset
                self.comparator = v;
                self.sync();
            });
        };

        this.initRadioValueWidget = function () {
            var self = this,
                field = this.field,
                vocab = field.vocabulary(),
                valueCell = $('td.value', this.target),
                inputName = this.targetId + '-' + field.name + '-value';
            vocab.forEach(function (term) {
                var value = term.value,
                    label = term.display_label(),
                    idiv = $('<div><input type="radio" /></div>'),
                    input = $('input', idiv),
                    termid = inputName + '-' + value;
                    input.attr('name', inputName)
                         .attr('id', termid)
                         .attr('value', term.value);
                    if (term.value === self.value) {
                        input.attr('checked', 'CHECKED');
                    }
                    $('<label>'+label+'</label>').attr('for', termid).appendTo(idiv);
                    idiv.appendTo(valueCell);
                    input.unbind().change(function () {
                        self.value = input.val();
                    });
            });
        };

        this.initSelectValueWidget = function () {
            var self = this,
                field = this.field,
                vocab = field.vocabulary(),
                select = $('<select />'),
                valueCell = $('td.value', this.target),
                inputName = this.targetId + '-' + field.name + '-value';
            select.attr('name', inputName);
            $('<option>').appendTo(select).val('EMPTY').text('-- SELECT A VALUE --');
            vocab.forEach(function (term) {
                var value = term.value,
                    label = term.display_label();
                $('<option>').appendTo(select).val(value).text(label);
            });
            if (typeof this.value === 'string') {
                select.val(this.value);
            }
            select.appendTo(valueCell);
            select.unbind().change(function () {
                self.value = select.val();
            });
        };

        this.initMultiValueWidget = function () {
            var self = this,
                field = this.field,
                vocab = field.vocabulary(),
                valueCell = $('td.value', this.target),
                inputName = this.targetId + '-' + field.name + '-value',
                currentValue = this.value,
                select = $('<select multiple="multiple">').appendTo(valueCell);
            vocab.forEach(function (term) {
                var option = $('<option>'),
                    label = term.display_label();
                option.appendTo(select).val(term.value).text(label);
                if (Array.isArray(self.value)) {
                    if ($.inArray(term.value, self.value) !== -1) {
                        option.attr('selected', 'selected');
                    }
                }
                select.unbind().change(function () {
                    self.value = select.val();
                });
            });
        };

        this.initInputValueWidget = function () {
            var self = this,
                field = this.field,
                valueCell = $('td.value', this.target),
                inputName = this.targetId + '-' + field.name + '-value',
                input = $('<input />');
            input.attr('name', inputName);
            input.attr('id', inputName);
            input.val(this.value);
            valueCell.append(input);
            input.unbind().change(function () {
                self.value = input.val();
            });
        };

        this.initValueWidget = function () {
            var self = this,
                valueCell = $('td.value', this.target),
                inputType = this.inputType(),
                initFn = {
                    radio: this.initRadioValueWidget,
                    select: this.initSelectValueWidget,
                    multi: this.initMultiValueWidget,
                    input: this.initInputValueWidget
                };
            valueCell.empty();
            if (!inputType) {
                return;
            }
            // pivot specific init function based on inputType
            initFn[inputType].call(this);
        };

        // hooks to sync dependent components
        this.preSync = function (observed) {};
        this.postSync = function (observed) {
            if (this.context && this.context.sync) {
                this.context.sync(this);
            }
        };
        this.syncTarget = function (observed) {
            var row = $(this.target),
                compareCell = $('td.compare', row),
                field = this.field,
                vocab;
            this.initFieldWidget();
            vocab = (field) ? this.comparators.vocabulary(field) : null;
            this.initComparatorWidget(vocab);
            this.initValueWidget();
        };

        this.init(options);
    };
    core.klass.subclasses(ns.FieldQuery, core.Item);

    /**
     * RecordFilter: Container of ordered FieldQuery objects
     */
    ns.RecordFilter = function (options) {

        initSchemaContext(this);

        Object.defineProperties(
            this,
            {
                operator: {
                    get: function () {
                        return this._operator || 'AND';
                    },
                    set: function (v) {
                        if (v !== 'AND' && v !== 'OR') {
                            throw new Error('invalid operator value');
                        }
                        this._operator = v;
                    }
                }
            }
        );

        this.syncQueryOpDisplay = function () {
            var table = $('table.queries', this.target),
                showrows = $('tr', table).not('.headings').slice(1),
                queryOpCells = $('td.display-queryop', showrows);
            queryOpCells.text(this.operator);
        };

        this.newQuery = function (options) {
            var opts = options || {},
                q = new ns.FieldQuery({
                    context: this,
                    field: opts.field,
                    comparator: opts.comparator,
                    value: opts.value
                });
            this.add(q);
            if (this.target) {
                this.syncQueryOpDisplay();
            }
            return q;
        };

        this.initView = function () {
            var self = this,
                target = $(this.target),
                innerhtml = $(ns.snippets.RECORDFILTER),
                addHandler = function () {
                    var btn = $(this);
                    self.newQuery();
                    self.sync();
                };
            if (!target.length) {
                throw new Error('no DOM target for record filter.');
            }
            target.attr('id', this.targetId);
            target.addClass('record-filter');
            target.empty();
            innerhtml.appendTo(target);
            $('a.addquery', target).unbind().click(addHandler);
            this.initQueryopInputs();
            this.sync();
        };

        this.init = function (options) {
            validateOptions(options);
            ns.RecordFilter.prototype.init.apply(this, [options]);
            this._schema = options.schema || undefined;
            this._comparators = options.comparators || undefined;
            if ($(this.target).length) {
                this.initView();
            }
        };


        // UI bits:

        this.syncQueryOperatorSelector = function () {
            var opdiv = $('div.queryop-selection', this.target);
            if (this.size() >= 2) {
                opdiv.show();
            } else {
                opdiv.hide();
            }
        };

        this.initQueryopInputs = function () {
            var self = this,
                opdiv = $('div.queryop-selection', this.target),
                opinputs = $('input', opdiv);
            this._operator = 'AND';
            opinputs.each(function () {
                var uid = self.id,
                    input = $(this),
                    baseid = input.attr('id'),
                    basename = input.attr('name');
                input.attr('name', basename + '-' + uid);
                input.attr('id', baseid + '-' + uid);
            });
            opinputs.unbind().change(function () {
                var showOp = (self.size() >= 2),
                    table = $('table.queries', self.target),
                    showrows = $('tr', table).not('.headings').slice(1),
                    queryOpCells = $('td.display-queryop', showrows),
                    operator = opinputs.filter(':checked').val() || 'AND';
                self.operator = operator;
                if (showOp) {
                    queryOpCells.text(self.operator);
                } else {
                    queryOpCells.text(' ');
                }
                self.sync();
            });
        };

        // hooks to sync dependent components
        this.preSync = function (observed) {};
        this.postSync = function (observed) {
            if (this.context && this.context.sync) {
                this.context.sync(this);
            }
        };
        this.syncTarget = function (observed) {
            var tbody = $('table.queries tbody', this.target),
                placeholder = $('tr.placeholder', tbody);
            if (this.size()) {
                placeholder.remove();
            } else {
                if (!placeholder.length) {
                    $(ns.snippets.PLACEHOLDER).appendTo(tbody);
                }
            }
            this.syncQueryOperatorSelector();
        };

        // container change hooks:
        this.afterAdd = function (key, value) {
            this.sync();
        };

        this.afterDelete = function (key, value) {
            this.sync();
        };

        this.onReorder = function (previous, current, note) {
            this.sync();
        };

        // factory methods for ns.FieldQuery objects contained:
        this.addQuery = function (options) {
            var query = new ns.FieldQuery(options);
        };

        this.isComplete = function () {
            var querycomplete = function (q) { return q.completionState(); };
            return (this.values().filter(querycomplete).length > 0);
        };

        // de-dupe checker, used by FieldQuery validation
        this.fieldnameInUse = function (name) {
            var qField = function (q) { return (q.field && q.field.name); },
                inUse = this.values().map(qField);
            return (inUse.indexOf(name) !== -1);
        };

        this.toJSON = function () {
            var payload = {},
                queries = this.values().filter(
                    function (query) {
                        return query.completionState();
                    },
                    this
                ).map(
                    function (query) {
                        return query.toJSON();
                    },
                    this
                );
            payload.uid = this.id;
            payload.operator = this.operator;
            payload.rows = queries;
            return payload;
        };

        this.init(options);
    };
    core.klass.subclasses(ns.RecordFilter, core.Container);

    /**
     * FilterGroup: Container of ordered RecordFilter objects
     */
    ns.FilterGroup = function (options) {

        initSchemaContext(this);

        this.init = function (options) {
            validateOptions(options);
            ns.FilterGroup.prototype.init.apply(this, [options]);
            this._schema = options.schema || undefined;
            this._comparators = options.comparators || undefined;
            this.operator = options.operator || 'union';
            if (this.target) {
                this.initView();
            }
        };

        this.opLabel = function () {
            return {
                'union': 'OR',
                'intersection': 'AND',
                'difference': 'MINUS / difference / relative complement)'
            }[this.operator] || 'OR';
        };

        this.newFilter = function () {
            var target = $('<div>').appendTo(this.target),
                rfilter = new ns.RecordFilter({
                    context: this,
                    target: target
                });
            this.add(rfilter);
            return rfilter;
        };

        this.initView = function () {
            var self = this,
                control = $(ns.snippets.GROUPCONTROL),
                addfilter = $('a.addfilter', control),
                opsel = $('.groupop-selection', control),
                opinputs = $('input', opsel);
            if (!(this.target instanceof $)) {
                return;
            }
            opinputs.unbind().change(function () {
                self.operator = $(this).val();
                self.sync();
            });
            this.target.addClass('filter-group');
            opinputs.each(function () {
                var uid = self.id,
                    input = $(this),
                    baseid = input.attr('id'),
                    basename = input.attr('name');
                input.attr('name', basename + '-' + uid);
                input.attr('id', baseid + '-' + uid);
            });
            addfilter.unbind().click(function () {
                self.newFilter();
            });
            control.appendTo(this.target);
        };

        this.postSync = function (observed) {
            if (this.context && this.context.sync) {
                this.context.sync(this);
            }
        };

        this.syncTarget = function (observed) {
            var self = this,
                target = this.target,
                operator = this.operator,
                opdisplay = $('<div class="groupop"></div>'),
                intermediate = $(this.values().slice(0, -1).map(function (v) {
                    return v.target[0];
                }, this));
            $('div.groupop', target).remove();
            opdisplay.text('(( ' + this.opLabel() + ' ))');
            intermediate.after(opdisplay);
            // finally make it possible to remove filters with buttons:
            $('a.removefilter', this.target).unbind().click(function () {
                var btn = $(this),
                    target = $(btn.parents('div.record-filter')[0]),
                    targetId = target.attr('id').split('_')[1];
                self.delete(targetId);
                target.remove();
            });
        };

        this.isComplete = function () {
            var filtercomplete = function (rfilter) {
                return rfilter.isComplete();
            };
            return (this.values().filter(filtercomplete).length > 0);
        };

        this.toJSON = function () {
            var payload = {},
                rfilters = this.values().filter(
                    function (rfilter) {
                        return rfilter.isComplete();
                    },
                    this
                ).map(
                    function (rfilter) {
                        return rfilter.toJSON();
                    },
                    this
                );
            payload.uid = this.id;
            payload.operator = this.operator;
            payload.filters = rfilters;
            return payload;
        };

        this.init(options);
    };
    core.klass.subclasses(ns.FilterGroup, core.Container);

    /**
     * ComposedQuery: Container of ordered FilterGroup objects
     */
    ns.ComposedQuery = function (options) {

        initSchemaContext(this);

        this.init = function (options) {
            validateOptions(options);
            ns.ComposedQuery.prototype.init.apply(this, [options]);
            this._schema = options.schema || undefined;
            this._comparators = options.comparators || undefined;
        };

        this.toJSON = function () {
            var payload = {},
                groups = this.values().filter(
                    function (group) {
                        return group.isComplete();
                    },
                    this
                ).map(
                    function (group) {
                        return group.toJSON();
                    },
                    this
                );
            payload.uid = this.id;
            payload.operator = this.operator;
            payload.groups = groups;
            return payload;
        };

        this.init(options);
    };
    core.klass.subclasses(ns.ComposedQuery, core.Container);


    // application initialization

    ns.initQuery = function (name, data) {
        var managerDiv = $('div.filter-manager'),
            wrapper = $('<div class="querywrap">').appendTo(managerDiv),
            h3title = $('<h3>' + name + '</h3>').appendTo(wrapper),
            target = $('<div>').appendTo(wrapper),
            saveContext = {
                // fake context to save/sync group
                sync: function (group) {
                    var groupExport = group.toJSON(),
                        composedExport = {
                            'name': name,
                            'operator': 'union',
                            'groups': groupExport
                        },
                        json = JSON.stringify(composedExport, null, 2),
                        form = $('#payloads'),
                        input = $('#payload-query-' + name);
                    input.val(json);  // save to payload input
                }
            },
            group = new ns.FilterGroup({
                target: target,
                schema: ns.schema,
                comparators: ns.comparators,
                operator: data.operator,
                context: saveContext
            });
        (data.filters || []).forEach(function (rf_data) {
            var rfilter = group.newFilter();
            rfilter.operator = rf_data.operator || 'AND';
            (rfilter.rows || []).forEach(function (rowdata) {
                var field = ns.schema.get(rowdata.field),
                    opts = {
                        field: field,
                        comparator: rowdata.comparator,
                        value: rowdata.value
                    };
                if (!field) {
                    console.log('WARNING: cannot find field ' + rowdata.field);
                    return;
                }
                rfilter.newQuery(opts);
            }, this);
        }, this);
    };

    ns.advancedEditorReady = function () {
        var managerDiv = $('div.filter-manager'),
            numq = $('form#payloads input#payload-query-numerator'),
            denq = $('form#payloads input#payload-query-denominator'),
            hasNum = (!!numq.length),
            hasDen = (!!denq.length),
            group;
        // get JSON data from (hidden) form inputs
        if (hasNum) {
            // setup numerator query, load
            numq = JSON.parse(numq.val());
            group = (numq.groups) ? numq.groups[0] : {};
            ns.initQuery('numerator', group);
        }
        if (hasDen) {
            denq = JSON.parse(denq.val());
            group = (denq.groups) ? denq.groups[0] : {};
            ns.initQuery('denominator', group);
        }

        // get target div for each field group
        // get each composed query payload from hidden form inputs
        // get data for first field group in each query
        // construct field group with target, data
        // set as ns.groups (key by num/den)
    };

    ns.initAdvancedEditor = function () {
        // load global configuration for editor, then call editorReady
        // as callback.
        ns.queries = {};
        cAjax({
            url: schemaURL(),
            success: function (data) {
                ns.schema = new uu.queryschema.Schema(data);
                ns.comparators = new uu.queryschema.Comparators(ns.schema);
                ns.advancedEditorReady();
            }
        });
    };

    // (interim) app init bits for testing only
    ns.initTesting = function () {
        var target1 = $('<div>').appendTo($('div.editor1')),
            target2 = $('<div>').appendTo($('div.editor2')),
            target3 = $('<div>').appendTo($('div.grouped')),
            schema = new uu.queryschema.Schema(uu.queryschema.mockSchema),
            comparators = new uu.queryschema.Comparators(schema),
            rfilter1 = new uu.queryeditor.RecordFilter({
                target: target1,
                schema: schema,
                comparators: comparators
            }),
            rfilter2 = new uu.queryeditor.RecordFilter({
                target: target2,
                schema: schema,
                comparators: comparators
            }),
            group = new uu.queryeditor.FilterGroup({
                target: target3,
                schema: schema,
                comparators: comparators
            });
        ns.group = group;  // TODO (testing)
    };

    $(document).ready(function () {
        if ($('body').attr('data-appname') === 'querytest') {
            ns.initTesting();
        }
        if ($('form#payloads').attr('data-editor') === 'advanced') {
            ns.initAdvancedEditor();
        }
    });

    return ns;

}(jQuery, uu.queryeditor || {}, uu, window[COREMODELNS], window));
