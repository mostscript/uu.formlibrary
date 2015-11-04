/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

var ruleseditor = (function ($) {
  "use strict";
  
  var ns = {},
      core = coremodel;
 
  ns.uuid4_tmpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
  ns.uuid4 = function () {
      return ns.uuid4_tmpl.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
  };
 
  ns.schema = null;
  ns.comparator = null;

  ns.snippets = {};

  ns.snippets.rule = '';  // should only be loaded on DOM ready

  ns.snippets.RULEMETA = '' +
    '<div class="rulemeta">\n' +
    '  <label>Rule title: </label>' +
    '  <input class="rule-title" type="text" size="80" /> <br />' +
    '  <label>Description / notes: </label>' +
    '  <textarea class="rule-description"></textarea>' +
    '</div>';
  
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

    this.ruleItem = function (k) {
      return $('#rule-' + k, this.target).parent();
    };

    this.afterDelete = function (k, v) {
      this.ruleItem(k).remove();  // sync dom, delete <li> element
      ns.FieldRules.prototype.afterDelete.apply(this, [k, v]);
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
      console.log(previous, current, note);
      ns.FieldRules.prototype.onReorder.apply(this, [previous, current, note]);
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
          choiceClick = this.menuChoiceClick.bind(this);
      // click handler for main menu button for rule:
      menuButton.click(function () {
        menu.toggle();
      });
      // click handlers on menu choices:
      $('li a', menu).click(function () {
        choiceClick(menu, $(this));
      });
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

    this.init = function (options) {
      ns.FieldRule.prototype.init.apply(this, [options]);
      options.target.attr('id', 'rule-' + this.id);
      this.initControls();
      this.initWhen();
      // TODO: init act
      // TODO: init otherwise
    }; 

    this.init(options);
  };
  core.klass.subclasses(ns.FieldRule, core.Item);

  ns.RuleAction = function RuleAction(options) {
 
    this.init = function (options) {
      ns.RuleAction.prototype.init.apply(this, [options]);
      this.schema = schema || ns.schema;
    };
 
    this.init(options);
  };
  core.klass.subclasses(ns.RuleAction, core.Item);

  // app init:

  ns.addRule = function () {
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

  ns.initEditor = function () {
    ns.initSnippets();
    ns.loadSchema(ns.ready);
  };

  document.addEventListener('DOMContentLoaded', ns.initEditor);

  return ns;

}(jQuery));
