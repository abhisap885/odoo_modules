from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..utils.ai_client import AIClient


class AIChat(models.Model):
    _name = "ai.chat"
    _description = "AI Chat Conversation"
    _order = "write_date desc"

    name = fields.Char(string="Title", required=True, default="New Conversation")
    user_id = fields.Many2one(
        "res.users", string="User", default=lambda self: self.env.user
    )
    provider_id = fields.Many2one("ai.provider", string="Provider")
    model = fields.Char(string="Model")
    message_ids = fields.One2many("ai.chat.message", "chat_id", string="Messages")
    message_count = fields.Integer(compute="_compute_message_count", store=True)
    token_count = fields.Integer(string="Tokens", default=0)

    @api.depends("message_ids")
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    def _get_provider(self):
        self.ensure_one()
        if self.provider_id:
            return self.provider_id
        company = self.env.company
        provider = self.env["ai.provider"].search(
            [("company_id", "=", company.id), ("active", "=", True)], limit=1
        )
        if not provider:
            provider = self.env["ai.provider"].search(
                [("active", "=", True)], limit=1
            )
        if not provider:
            raise UserError(
                _("No active AI provider configured. Please add one in Settings.")
            )
        return provider

    def action_ask(self, user_message):
        """Append a user message and stream back the assistant reply text."""
        self.ensure_one()
        provider = self._get_provider()
        self.provider_id = provider.id
        self.model = provider.model

        self.env["ai.chat.message"].create(
            {"chat_id": self.id, "role": "user", "content": user_message}
        )

        messages = [
            {"role": m.role, "content": m.content}
            for m in self.message_ids
        ]
        try:
            client = AIClient(
                provider.provider,
                provider._decrypt_key(provider.api_key),
                provider.model,
                provider.base_url or None,
            )
            reply = client.chat(
                messages,
                temperature=provider.temperature,
                max_tokens=provider.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise UserError(_("AI request failed: %s") % exc)

        self.env["ai.chat.message"].create(
            {"chat_id": self.id, "role": "assistant", "content": reply}
        )
        # Rough token estimate (4 chars ~ 1 token) for cost tracking.
        est_tokens = len(reply) // 4
        self.token_count += est_tokens
        provider.action_increase_tokens(est_tokens)
        return reply


class AIChatMessage(models.Model):
    _name = "ai.chat.message"
    _description = "AI Chat Message"
    _order = "sequence, id"

    chat_id = fields.Many2one(
        "ai.chat", string="Chat", ondelete="cascade", required=True
    )
    role = fields.Selection(
        [("system", "System"), ("user", "User"), ("assistant", "Assistant")],
        string="Role",
        required=True,
        default="user",
    )
    content = fields.Text(string="Content", required=True)
    sequence = fields.Integer(default=10)
