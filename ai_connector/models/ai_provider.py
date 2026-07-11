from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..utils import encryption
from ..utils.ai_client import (
    AIClient,
    DEFAULT_MODELS,
    DEFAULT_EMBEDDING_MODELS,
    EMBEDDING_CAPABLE,
)


class AIProvider(models.Model):
    _name = "ai.provider"
    _description = "AI Provider"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True, translate=True)
    provider = fields.Selection(
        [
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic Claude"),
            ("gemini", "Google Gemini"),
            ("mistral", "Mistral AI"),
            ("ollama", "Ollama (local)"),
        ],
        string="Provider",
        required=True,
        default="openai",
    )
    api_key = fields.Char(string="API Key", help="Stored encrypted at rest.")
    api_key_test = fields.Char(
        string="API Key (test)",
        help="Temporary key used only for the 'Test Connection' action.",
    )
    model = fields.Char(
        string="Model",
        required=True,
        help="e.g. gpt-4o-mini, claude-3-5-sonnet-latest, gemini-1.5-flash, llama3.1",
    )
    base_url = fields.Char(
        string="Base URL",
        help="Override the default endpoint (useful for proxies or Ollama).",
    )
    temperature = fields.Float(default=0.7)
    max_tokens = fields.Integer(default=1024)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    total_tokens_used = fields.Integer(string="Total Tokens Used", readonly=True, default=0)
    last_error = fields.Text(readonly=True)
    notes = fields.Text()

    embedding_model = fields.Char(
        string="Embedding Model",
        help="Model used to create vectors for RAG (e.g. text-embedding-3-small).",
    )
    supports_embeddings = fields.Boolean(
        string="Supports Embeddings",
        compute="_compute_supports_embeddings",
        store=True,
    )

    _sql_constraints = [
        (
            "uniq_name_company",
            "unique(name, company_id)",
            "Provider names must be unique per company.",
        )
    ]

    @api.onchange("provider")
    def _onchange_provider(self):
        for rec in self:
            rec.model = DEFAULT_MODELS.get(rec.provider, rec.model)
            rec.embedding_model = DEFAULT_EMBEDDING_MODELS.get(rec.provider, False)

    @api.depends("provider")
    def _compute_supports_embeddings(self):
        for rec in self:
            rec.supports_embeddings = rec.provider in EMBEDDING_CAPABLE

    # ------------------------------------------------------------------ #
    # Encryption helpers
    # ------------------------------------------------------------------ #
    def _decrypt_key(self, key):
        if not key:
            return key
        try:
            return encryption.decrypt(key, self.env)
        except Exception:
            # Already plaintext (e.g. legacy value) – keep as-is.
            return key

    def _encrypt_key(self, key):
        if not key:
            return key
        return encryption.encrypt(key, self.env)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("api_key"):
                vals["api_key"] = encryption.encrypt(vals["api_key"], self.env)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("api_key"):
            vals["api_key"] = encryption.encrypt(vals["api_key"], self.env)
        return super().write(vals)

    # ------------------------------------------------------------------ #
    # Client build / test
    # ------------------------------------------------------------------ #
    def _get_client(self, api_key=None):
        self.ensure_one()
        key = api_key or self._decrypt_key(self.api_key)
        if not key and self.provider != "ollama":
            raise UserError(_("No API key configured for provider %s.") % self.name)
        return AIClient(
            provider=self.provider,
            api_key=key,
            model=self.model,
            base_url=self.base_url or None,
        )

    def action_test_connection(self):
        self.ensure_one()
        key = self.api_key_test or self._decrypt_key(self.api_key)
        if not key and self.provider != "ollama":
            raise UserError(_("Provide an API key to test the connection."))
        try:
            client = AIClient(
                self.provider, key, self.model, self.base_url or None
            )
            client.chat(
                [{"role": "user", "content": "Say 'OK' in one word."}],
                temperature=0,
                max_tokens=10,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            raise UserError(_("Connection failed: %s") % exc)
        self.last_error = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection successful"),
                "message": _("Provider %s is reachable.") % self.name,
                "type": "success",
            },
        }

    def action_increase_tokens(self, amount):
        self.sudo().write({"total_tokens_used": self.total_tokens_used + amount})
