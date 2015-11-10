/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

var ruleseditor = (function ($) {
  "use strict";
  
  var ns = {},
      core = coremodel,
      maxIndex = Math.pow(2, 31) - 1;  // max css z-index in 32-bit browsers
 
  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };
 
  ns.schema = null;
  ns.comparator = null;

  // Actions vocabulary for drop-down:
  ns.actions = {
    disable: {
      title: 'Disable field',
      description: 'Field will be presented on form inaccessible to input ' +
                   'and will be grayed out, marked as N/A.'
    },
    enable: {
      title: 'Enable field',
      description: 'Field will be enabled if previously disabled by rule.'
    },
    highlight: {
      title: 'Highlight field',
      description: 'Highlight a field using a background-color and optional ' +
                   'message, which can be configured here.'
    },
    remove_highlights: {
      title: 'Remove highlight',
      description: 'Any highlight set by previously by a rule will be removed.'
    }
  };

  ns.snippets = {};

  ns.snippets.rule = '';  // should only be loaded on DOM ready

  ns.snippets.RULEMETA = '' +
    '<div class="rulemeta">\n' +
    '  <label>Rule title: </label>' +
    '  <input class="rule-title" type="text" size="80" /> <br />' +
    '  <label>Description / notes: </label>' +
    '  <textarea class="rule-description"></textarea>' +
    '</div>';
 
  ns.snippets.ACTION = '' + 
    '<li class="rule-action">' +
    '  <table class="action-spec">\n' +
    '    <tr>\n' +
    '      <th class="action-header-field">Affected field</th>\n' +
    '      <th class="action-header-act">Action to take</th>\n' + 
    '    </tr>\n' +
    '    <tr>\n' +
    '      <td class="action-cell-field"></td>\n' + 
    '      <td class="action-cell-act"></td>\n' + 
    '    </tr>\n' +
    '    <tr>\n' +
    '     <td class="action-cell-extras" colspan="2"></td>\n' +
    '    </tr>\n' +
    '  </table>\n' +
    '  <div class="action-control">\n' +
    '    <a class="action-remove-link" href="javascript:void(0)">×</a>' +
    '  </div>\n' +
    '</li>\n';

  ns.snippets.WHENTITLE = '<h3>When following condition(s) are met:</h3>';

  // Core model for rules editor:

  ns.FieldRules = function FieldRules(options) {

    this.init = function (options) {
      ns.FieldRules.prototype.init.apply(this, [options]);
    }; 

    this.newRule = function () {
      var item = $('<li>').appendTo(this.target),
          ruleUid = ns.uuid4(),
          ruleTarget = $(ns.snippets.rule).appendTo(item),
          rule = new ns.FieldRule({
            target: ruleTarget,
            context: this,
            id: ruleUid
          });
      this.add(rule);
    };

    this.collapseAll = function () {
      this.values().forEach(function (rule) {
        rule.collapse();
      });
    };

    this.expandAll = function () {
      this.values().forEach(function (rule) {
        rule.expand();
      });
    };

    this.tableOfContents = function () {
      /** returns ToC data as id, title pairs */
      return this.values().map(
        function (rule) {
          var target = rule.target,
              title = $('.rule-title', target).val();
          return {
            id: rule.id,
            rule: rule,
            title: title
          };
        }
      );
    };

    this.afterDelete = function (k, v) {
      v.target.parent().remove();  // remove li wrapping target div
      ns.FieldRules.prototype.afterDelete.apply(this, [k, v]);
    };

    this.ruleItem = function (k) {
      return $('#rule-' + k, this.target).parent();
    };

    this.onReorder = function (previous, current, note) {
      var listing = this.target;
      // for each rule uid, get DOM node in FIFO, move to bottom:
      current.forEach(function (k) {
        var ruleItem = this.ruleItem(k);
        listing.append(ruleItem);
        },
        this
      );
      ns.FieldRules.prototype.onReorder.apply(this, [previous, current, note]);
    };

    this.syncTOC = function () {
      var data = this.tableOfContents(),
          tocTarget = $('.rules-toc', this.target.parent()),
          listing = $('<ol class="rule-links">');
      tocTarget.empty();
      listing.appendTo(tocTarget);
      data.forEach(function (linkData, i) {
          var href = '#rule-' + linkData.id,
              item = $('<li>').appendTo(listing),
              link = $('<a class="toc-link">').appendTo(item);
          link.attr('href', href);
          link.text(linkData.title || ' (Untitled rule)');
          link.click(function () {
            linkData.rule.context.collapseAll();
            linkData.rule.expand();
          });
        },
        this
      );
    };

    this.syncTarget = function (observed) {
      if (!(observed instanceof ns.FieldRule)) {
        // sync table of contents
        this.syncTOC();  // only on effect of container event, not rule ctor
        // adjust z-index (decrementing) on list items within:
        this.values().forEach(function (rule, idx) {
          var item = rule.target.parent();
          item.css({
            'position': 'relative',
            'z-index': '' + (maxIndex - idx)
          });
        });
      }
    };

    this.init(options);

  };
  core.klass.subclasses(ns.FieldRules, core.Container);

  ns.FieldRule = function FieldRule(options) {

    this.remove = function () {
      this.context.delete(this.id);
    };

    this.moveUp = function () {
      this.context.order.moveUp(this.id);
    };

    this.moveDown = function () {
      this.context.order.moveDown(this.id);
    };

    this.moveToTop = function () {
      this.context.order.moveToTop(this.id);
    };

    this.moveToBottom = function () {
      this.context.order.moveToBottom(this.id);
    };

    this.collapse = function () {
      this.target.parent().addClass('collapsed');
    };

    this.expand = function (exclusive) {
      if (exclusive) {
        this.context.collapseAll();
      }
      this.target.parent().removeClass('collapsed');
    };

    this.menuChoiceClick = function (menu, link) {
      // dispatch based on classname of context
      var handlers = {
          'move-up': this.moveUp,
          'move-down': this.moveDown,
          'move-top': this.moveToTop,
          'move-bottom': this.moveToBottom,
          'delete-rule': this.remove
        },
        handler;
      Object.keys(handlers).forEach(function (k) {
          if (link.hasClass(k)) {
            handler = handlers[k];
          }
        },
        this
      );
      if (handler) {
        handler.bind(this)();
        if (!link.hasClass('delete-rule')) {
          menu.toggle();
        }
      }
    };

    this.initControls = function () {
      var menuButton = $('a.menubutton', this.target),
          menu = $('ul.menu-choices', this.target),
          choiceClick = this.menuChoiceClick.bind(this),
          self = this,
          expand = function () { self.expand(true); };
      // click handler for main menu button for rule:
      menuButton.click(function () {
        menu.toggle();
      });
      // click handlers on menu choices:
      $('li a', menu).click(function () {
        choiceClick(menu, $(this));
      });
      // TOC sync on title edit:
      $('.rule-meta .rule-title', this.target).on('input', function () {
        self.context.syncTOC();
      });
      // make sure (only) this rule is expanded if title focused:
      $('.rule-meta .rule-title', this.target).on('focus', expand);
      // clicking on a rule should expand it:
      this.target.parent().click(expand);
    };

    this.initWhen = function () {
      var uid = ns.uuid4(),
          whenTarget = $('.rule-when .when', this.target);
        whenTarget.attr('id', uid);
      this.critEditor = new uu.queryeditor.RecordFilter({
        context: this,
        schema: ns.schema,
        comparators: ns.comparators,
        target: whenTarget,
        namespace: 'fieldrule-criteria',
        id: uid
      });
    };

    this.initAct = function () {
      var container = $('.rule-part.rule-act', this.target),
          listing = $('ul.actions', container),
          self = this;
      this.actions = new ns.RuleActions({
        context: this,
        target: listing,
        schema: ns.schema,
        namespace: 'fieldrule-act',
        id: ns.uuid4()
      });
    };

    this.initOtherwise = function () {
      var otherwiseTarget = $('.rule-part.rule-otherwise ul.actions', this.target);
      this.otherwise = new ns.RuleActions({
        context: this,
        target: otherwiseTarget,
        schema: ns.schema,
        namespace: 'fieldrule-otherwise',
        id: ns.uuid4()
      });
    };

    this.init = function (options) {
      ns.FieldRule.prototype.init.apply(this, [options]);
      options.target.attr('id', 'rule-' + this.id);
      this.initControls();
      // init "when" clause (record filter):
      this.initWhen();
      // init "act"
      this.initAct();
      // init "otherwise"
      this.initOtherwise();
      // Go to rule:
      window.location.hash = 'rule-' + this.id;
    }; 

    this.position = function () {
      /** position of this rule in its parent, calculated */
      return this.context.keys().indexOf(this.id);
    };

    this.init(options);
  };
  core.klass.subclasses(ns.FieldRule, core.Item);

  ns.RuleAction = function RuleAction(options) {

    this.init = function (options) {
      ns.RuleAction.prototype.init.apply(this, [options]);
      this.schema = options.schema || ns.schema;
      this.initUI();
   };

    this.remove = function () {
      this.context.delete(this.id);
    };

    this.initFieldChoices = function () {
      var cell = $('.action-cell-field', this.target),
          select = $('<select class="action-field">').appendTo(cell);
      $('<option>--Select a value--</option>').appendTo(select);
      ns.schema.keys().forEach(function (fieldname) {
          var field = ns.schema.get(fieldname),
              option = $('<option>').appendTo(select);
          option.attr({
            value: fieldname
          });
          option.text(field.title);
        },
        this
      );
    };

    this.initActionChoices = function () {
      var cell = $('.action-cell-act', this.target),
          select = $('<select class="action-type">').appendTo(cell);
      Object.keys(ns.actions).forEach(function (key) {
          var option = $('<option>').appendTo(select),
              meta = ns.actions[key];
          option.attr({
            value: key,
            title: meta.description
          });
          option.text(meta.title);
        },
        this
      );
    };


    this.loadExtras = function () {
      var cell = $('.action-cell-extras', this.target),
          properties = [
            {
              name: 'color',
              label: 'Color',
              default: '#ff9'
            },
            {
              name: 'message',
              label: 'Message (optional)'
            }
          ];
      properties.forEach(function (actprop) {
          var div = $('<div class="actprop">').appendTo(cell),
              label = $('<label>').appendTo(div),
              isColor = actprop.name === 'color',
              inputTag = (isColor) ? '<input type="color">' : '<input>',
              input = $(inputTag).appendTo(div); 
          label.text(actprop.label);
          if (actprop.name === 'color') {
            div.css('border-right', '1em solid ' + actprop.default);
            input.change(function () {
              var color = input.val();
              div.css('border-right', '1em solid ' + color);
            });
          }  
        },
        this
      );
      cell.show();
    };

    this.initExtras = function () {
      var cell = $('.action-cell-act', this.target),
          select = $('.action-type', cell),
          self = this;
      select.change(function () {
        var choice = select.val();
        if (choice === 'highlight') {
          self.loadExtras();
        }
      });
    };

    this.initUI = function () {
      var self = this;
      // set id based on namespace, id:
      this.target.attr('id', this.targetId);
      // init control (delete button):
      $('a.action-remove-link', this.target).click(function () {
        self.remove();
      });
      this.initFieldChoices();
      this.initActionChoices();
      this.initExtras();
      // add first row TODO to table in snippet
      // hookup field chooser
      // hookup actions chooser with choices: enable, disable, highlight, clear_highlights
      // hookup actions extras in second row ?? or defer until extras applicable
    };

    this.init(options);
  };
  core.klass.subclasses(ns.RuleAction, core.Item);

  ns.RuleActions = function RuleActions(options) {
 
    this.init = function (options) {
      var self = this;
      ns.RuleActions.prototype.init.apply(this, [options]);
      $('a.add-action', this.target.parent()).click(function () {
        self.newAction();
      });
    };

    this.afterDelete = function (k, v) {
      v.target.remove();  // sync dom, delete <li> element 
      ns.RuleActions.prototype.afterDelete.apply(this, [k, v]);
    };

    this.newAction = function () {
      var item = $(ns.snippets.ACTION).appendTo(this.target);
      this.add(new ns.RuleAction({
        context: this,
        target: item,
        schema: ns.schema,
        namespace: 'fieldrule-action',
        id: ns.uuid4()
      }));
    };

    this.init(options);
  };
  core.klass.subclasses(ns.RuleActions, core.Container);

  // app init:

  ns.addRule = function () {
    ns.rules.collapseAll();
    ns.rules.newRule();
  };

  ns.initHandlers = function () {
    // TODO: implement handler(s)
    var addBtn = $('a.addrule');
    addBtn.click(ns.addRule);
  };

  ns.ready = function (data) {
    ns.schema = new uu.queryschema.Schema(data.entries);
    ns.comparators = new uu.queryschema.Comparators(ns.schema);
    ns.rules = new ns.FieldRules({
      target: $('#fieldrules')
    });
    ns.initHandlers();
  };

  ns.loadSchema = function (callback) {
    uu.queryschema.cAjax({
      url: '@@schemajson',
      success: callback
    });
  };

  ns.initSnippets = function () {
    var ruleSnippet = $('script#rule-snippet').html();
    ns.snippets.rule = ruleSnippet;
  };

  ns.pageFixes = function () {
    $('base', $('head')).remove();
  };

  ns.initEditor = function () {
    ns.pageFixes();
    ns.initSnippets();
    ns.loadSchema(ns.ready);
  };

  document.addEventListener('DOMContentLoaded', ns.initEditor);

  return ns;

}(jQuery));
