from odoo import models, fields, api, _


class AIConnectorWizard(models.TransientModel):
    _name = "ai.connector.wizard"
    _description = "AI Connector Quick Ask Wizard"

    provider_id = fields.Many2one("ai.provider", string="Provider")
    template_id = fields.Many2one("ai.prompt.template", string="Template")
    question = fields.Text(string="Your Question", required=True)
    answer = fields.Text(string="AI Response", readonly=True)
    chat_id = fields.Many2one("ai.chat", string="Conversation")

    @api.onchange("template_id")
    def _onchange_template(self):
        if self.template_id and self.template_id.prompt:
            # Pre-fill the question with the template prompt for convenience.
            if not self.question:
                self.question = self.template_id.prompt

    def action_ask(self):
        self.ensure_one()
        company = self.env.company
        provider = (
            self.provider_id
            or self.template_id.provider_id
            or self.env["ai.provider"].search(
                [("company_id", "=", company.id), ("active", "=", True)], limit=1
            )
            or self.env["ai.provider"].search([("active", "=", True)], limit=1)
        )
        if not provider:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No provider"),
                    "message": _("Configure an active AI provider first."),
                    "type": "danger",
                },
            }

        # Create / reuse a conversation so history is preserved.
        if not self.chat_id:
            self.chat_id = self.env["ai.chat"].create({"name": "Quick Ask"})
        reply = self.chat_id.action_ask(self.question)
        self.answer = reply
        # Re-open the wizard showing the answer.
        return {
            "type": "ir.actions.act_window",
            "res_model": "ai.connector.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
