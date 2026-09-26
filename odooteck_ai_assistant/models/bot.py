import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OTAIBot(models.Model):
    _name = "ot.ai.bot"
    _description = "AI Assistant"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    website_enabled = fields.Boolean(default=True)
    provider_id = fields.Many2one("ot.ai.provider", string="Primary provider")
    fallback_provider_id = fields.Many2one("ot.ai.provider", string="Fallback provider")
    response_mode = fields.Selection([("grounded", "Knowledge only"), ("hybrid", "Knowledge and AI"),
                                      ("general", "General AI")], default="grounded", required=True)
    welcome_message = fields.Char(default="Hi! How can I help you today?")
    fallback_message = fields.Char(default="I could not find a reliable answer. Please ask for a human agent.")
    system_prompt = fields.Text(default="You are a helpful shopping assistant. Answer clearly and briefly. Never invent product availability, prices or policies.")
    knowledge_ids = fields.One2many("ot.ai.knowledge", "bot_id")
    shared_knowledge_bot_ids = fields.Many2many(
        "ot.ai.bot", "ot_ai_bot_shared_knowledge_rel", "bot_id", "source_bot_id",
        string="Use knowledge from", help="Use approved knowledge maintained for these other assistants too.")

    def action_import_knowledge(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Import knowledge"),
                "res_model": "ot.ai.knowledge.import", "view_mode": "form", "target": "new",
                "context": {"default_bot_id": self.id}}
    max_history_turns = fields.Integer(default=6)
    max_requests_per_minute = fields.Integer(default=10)
    daily_token_budget = fields.Integer(help="0 means unlimited")
    daily_cost_budget = fields.Float(help="USD, 0 means unlimited")
    allow_product_search = fields.Boolean(default=True)
    handoff_keywords = fields.Char(default="human,agent,person,representative,insaan")
    auto_handoff_after_negative = fields.Integer(default=2)
    redact_pii = fields.Boolean(default=True)
    responsible_user_id = fields.Many2one("res.users", string="Budget owner", default=lambda self: self.env.user)

    @api.constrains("provider_id", "fallback_provider_id")
    def _check_fallback(self):
        for bot in self:
            if bot.provider_id and bot.provider_id == bot.fallback_provider_id:
                raise ValidationError(_("Choose a different fallback provider."))

    def wants_human(self, query):
        self.ensure_one()
        words = [word.strip().casefold() for word in (self.handoff_keywords or "").split(",") if word.strip()]
        text = (query or "").casefold()
        return any(re.search(r"\b%s\b" % re.escape(word), text) for word in words)

    def _daily_usage(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        rows = self.env["ot.ai.message"].sudo().read_group(
            [("bot_id", "=", self.id), ("create_date", ">=", str(today)), ("role", "=", "assistant")],
            ["total_tokens:sum", "cost_usd:sum"], [])
        return rows[0] if rows else {}

    def _budget_available(self):
        usage = self._daily_usage()
        return not ((self.daily_token_budget and usage.get("total_tokens", 0) >= self.daily_token_budget)
                    or (self.daily_cost_budget and usage.get("cost_usd", 0) >= self.daily_cost_budget))
