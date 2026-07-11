from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_default_provider_id = fields.Many2one(
        "ai.provider",
        string="Default AI Provider",
        help="Provider used when no provider is explicitly chosen.",
        config_parameter="ai_connector.default_provider_id",
    )
    ai_embedding_provider_id = fields.Many2one(
        "ai.provider",
        string="Embedding Provider",
        domain="[('supports_embeddings','=',True)]",
        help="Provider used to create vectors for the RAG product knowledge base.",
        config_parameter="ai_connector.embedding_provider_id",
    )
    ai_chunk_size = fields.Integer(
        string="Chunk Size (chars)",
        default=800,
        config_parameter="ai_connector.chunk_size",
    )
    ai_rag_top_k = fields.Integer(
        string="RAG Top-K",
        default=3,
        config_parameter="ai_connector.rag_top_k",
        help="Number of product chunks retrieved per question.",
    )
    ai_secret_stored = fields.Boolean(
        string="Secrets Encrypted",
        compute="_compute_ai_secret_stored",
        help="Whether a secret key has been configured for encryption.",
    )

    @api.model
    def _compute_ai_secret_stored(self):
        for rec in self:
            rec.ai_secret_stored = bool(
                self.env["ir.config_parameter"].sudo().get_param("ai_connector.secret")
            )
