odoo.define("ai_connector.ChatWidget", function (require) {
    "use strict";

    var core = require("web.core");
    var Widget = require("web.Widget");
    var rpc = require("web.rpc");
    var QWeb = core.qweb;
    var _t = core._t;

    var ChatWidget = Widget.extend({
        template: "ai_connector.ChatPanel",
        events: {
            "click .o_ai_send": "_onSend",
            "keypress .o_ai_input": "_onKeypress",
        },

        start: function () {
            this._super.apply(this, arguments);
            this.messages = [];
            this.chat_id = null;
            this._render();
        },

        _render: function () {
            this.$(".o_ai_messages").html(
                QWeb.render("ai_connector.ChatMessages", {messages: this.messages})
            );
        },

        _onKeypress: function (e) {
            if (e.which === 13 && !e.shiftKey) {
                e.preventDefault();
                this._onSend();
            }
        },

        _onSend: function () {
            var self = this;
            var $input = this.$(".o_ai_input");
            var text = $input.val().trim();
            if (!text) {
                return;
            }
            $input.val("");
            this.messages.push({role: "user", content: text});
            this.messages.push({role: "assistant", content: _t("Thinking...")});
            this._render();

            rpc.query({
                route: "/ai_connector/chat",
                params: {
                    chat_id: this.chat_id,
                    message: text,
                },
            }).then(function (result) {
                if (result.error) {
                    self.messages.pop();
                    self.messages.push({role: "assistant", content: "Error: " + result.error});
                } else {
                    self.chat_id = result.chat_id;
                    self.messages.pop();
                    self.messages.push({role: "assistant", content: result.reply});
                }
                self._render();
                self.$(".o_ai_messages").scrollTop(self.$(".o_ai_messages")[0].scrollHeight);
            });
        },
    });

    // Register the client action so the menu item works across Odoo versions.
    if (core.action_registry) {
        core.action_registry.add("ai_connector_chat", ChatWidget);
    } else {
        try {
            require("registry").category("actions").add("ai_connector_chat", ChatWidget);
        } catch (e) {
            console.warn("AI Connector: could not register client action", e);
        }
    }

    return ChatWidget;
});
