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
            title: title
          };
        }
      );
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

    this.expand = function () {
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
          self = this;
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
