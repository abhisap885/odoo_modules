from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AIPromptTemplate(models.Model):
    _name = "ai.prompt.template"
    _description = "AI Prompt Template"
    _order = "name"

    name = fields.Char(string="Name", required=True, translate=True)
    category = fields.Selection(
        [
            ("general", "General"),
            ("sales", "Sales"),
            ("crm", "CRM"),
            ("hr", "HR"),
            ("marketing", "Marketing"),
            ("support", "Support"),
        ],
        string="Category",
        default="general",
    )
    provider_id = fields.Many2one(
        "ai.provider",
        string="Default Provider",
        help="Leave empty to use the company default provider.",
    )
    system_message = fields.Text(
        string="System Message",
        help="High-level instructions sent to the model.",
    )
    prompt = fields.Text(
        string="Prompt",
        required=True,
        help="Use {{variable}} placeholders, e.g. {{record_name}} or {{description}}.",
    )
    variable_ids = fields.One2many(
        "ai.prompt.variable", "template_id", string="Variables"
    )
    model = fields.Char(string="Model Override")
    temperature = fields.Float(default=0.7)
    active = fields.Boolean(default=True)

    def render_prompt(self, context=None):
        """Replace ``{{var}}`` placeholders using ``context`` values."""
        self.ensure_one()
        context = context or {}
        prompt = self.prompt or ""
        for var in self.variable_ids:
            token = "{{%s}}" % var.name
            prompt = prompt.replace(token, str(context.get(var.name, "")))
        # Strip any unresolved placeholders so the model is not confused.
        import re

        prompt = re.sub(r"\{\{\s*[\w.]+\s*\}\}", "", prompt)
        return prompt.strip()

    def build_messages(self, context=None):
        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.append({"role": "user", "content": self.render_prompt(context)})
        return messages

    def action_test_render(self):
        self.ensure_one()
        rendered = self.render_prompt()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Rendered Prompt"),
                "message": rendered[:500] or _("(empty)"),
                "type": "info",
            },
        }


class AIPromptVariable(models.Model):
    _name = "ai.prompt.variable"
    _description = "AI Prompt Variable"
    _order = "name"

    name = fields.Char(string="Variable", required=True)
    description = fields.Char(string="Description")
    template_id = fields.Many2one(
        "ai.prompt.template", string="Template", ondelete="cascade"
    )
