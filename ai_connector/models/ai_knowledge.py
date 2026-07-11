import json
import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..utils.ai_client import get_embedding, EMBEDDING_CAPABLE


def _chunk_text(text, size=800, overlap=120):
    """Split ``text`` into overlapping character chunks for embedding."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += size - overlap
    return [c for c in chunks if c]


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class AIProductEmbedding(models.Model):
    _name = "ai.product.embedding"
    _description = "AI Product Embedding (RAG)"
    _order = "product_tmpl_id, chunk_index"

    name = fields.Char(string="Chunk Title", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Product", ondelete="cascade", required=True
    )
    chunk_index = fields.Integer(string="Chunk #", default=0)
    content = fields.Text(string="Chunk Text", required=True)
    embedding = fields.Text(
        string="Embedding Vector",
        help="JSON-encoded vector. Never shown in the UI for performance.",
    )
    similarity = fields.Float(string="Similarity", compute="_compute_similarity")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    _sql_constraints = [
        (
            "uniq_product_chunk",
            "unique(product_tmpl_id, chunk_index)",
            "Each product chunk must be unique.",
        )
    ]

    def _compute_similarity(self):
        # Placeholder; real similarity is computed in search_similar().
        for rec in self:
            rec.similarity = 0.0

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #
    def _build_product_text(self, product):
        lines = [
            "Product: %s" % (product.name or ""),
            "Internal Reference: %s" % (product.default_code or ""),
            "Category: %s" % (product.categ_id.complete_name if product.categ_id else ""),
            "Price: %s %s" % (product.list_price, product.currency_id.name or ""),
            "Type: %s" % (product.detailed_type or ""),
        ]
        attrs = []
        for line in product.attribute_line_ids:
            vals = ", ".join(line.value_ids.mapped("name"))
            if vals:
                attrs.append("%s: %s" % (line.attribute_id.name, vals))
        if attrs:
            lines.append("Attributes: " + "; ".join(attrs))
        desc = product.website_description or product.description_sale or product.description
        if desc:
            lines.append("Description: " + desc)
        tags = ", ".join(product.product_tag_ids.mapped("name"))
        if tags:
            lines.append("Tags: " + tags)
        return "\n".join(lines)

    def index_product(self, product, provider=None):
        """(Re)create embedding chunks for a single product."""
        provider = provider or self.env["ai.provider"].get_embedding_provider()
        if not provider:
            raise UserError(
                _("No embedding provider configured. Set one in Settings > AI Connector.")
            )
        text = self._build_product_text(product)
        chunk_size = int(
            self.env["ir.config_parameter"].sudo().get_param("ai_connector.chunk_size", 800)
        )
        chunks = _chunk_text(text, size=chunk_size)
        if not chunks:
            return
        key = provider._decrypt_key(provider.api_key)
        # Remove old chunks first.
        self.search([("product_tmpl_id", "=", product.id)]).unlink()
        recs = []
        for i, chunk in enumerate(chunks):
            vector = get_embedding(
                provider.provider,
                key,
                provider.embedding_model,
                chunk,
                provider.base_url or None,
            )
            recs.append(
                self.create(
                    {
                        "name": "%s (#%s)" % (product.name, i + 1),
                        "product_tmpl_id": product.id,
                        "chunk_index": i,
                        "content": chunk,
                        "embedding": json.dumps(vector),
                    }
                )
            )
        product.ai_indexed = True
        product.ai_indexed_date = fields.Datetime.now()
        return recs

    # ------------------------------------------------------------------ #
    # Bulk indexing
    # ------------------------------------------------------------------ #
    @api.model
    def index_all(self, limit=None):
        """(Re)index all sellable products. Used by the cron and the UI button."""
        provider = self.env["ai.provider"].get_embedding_provider()
        if not provider:
            raise UserError(
                _("No embedding provider configured. Set one in Settings > AI Connector.")
            )
        products = self.env["product.template"].search([("sale_ok", "=", True)])
        if limit:
            products = products[:limit]
        done = 0
        for product in products:
            self.index_product(product, provider)
            done += 1
        return done

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def search_similar(self, query_vector, limit=3, product_ids=None):
        """Return the top-``limit`` most similar chunks to ``query_vector``."""
        domain = []
        if product_ids:
            domain.append(("product_tmpl_id", "in", list(product_ids)))
        candidates = self.search(domain)
        scored = []
        for rec in candidates:
            try:
                vec = json.loads(rec.embedding)
            except (ValueError, TypeError):
                continue
            scored.append((_cosine(query_vector, vec), rec))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [r for _, r in scored[:limit]], (scored[0][0] if scored else 0.0)


class AIProvider(models.Model):
    _inherit = "ai.provider"

    @api.model
    def get_embedding_provider(self):
        """Resolve the configured embedding provider for the current company."""
        company = self.env.company
        provider = self.search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("provider", "in", EMBEDDING_CAPABLE),
                ("embedding_model", "!=", False),
            ],
            limit=1,
        )
        if not provider:
            provider = self.search(
                [
                    ("active", "=", True),
                    ("provider", "in", EMBEDDING_CAPABLE),
                    ("embedding_model", "!=", False),
                ],
                limit=1,
            )
        return provider


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ai_indexed = fields.Boolean(string="Indexed for AI", readonly=True, copy=False)
    ai_indexed_date = fields.Datetime(string="AI Indexed On", readonly=True, copy=False)
    ai_chunk_count = fields.Integer(
        string="AI Chunks", compute="_compute_ai_chunk_count", store=False
    )

    def _compute_ai_chunk_count(self):
        for rec in self:
            rec.ai_chunk_count = self.env["ai.product.embedding"].search_count(
                [("product_tmpl_id", "=", rec.id)]
            )

    def action_ai_index(self):
        provider = self.env["ai.provider"].get_embedding_provider()
        if not provider:
            raise UserError(
                _("No embedding provider configured. Set one in Settings > AI Connector.")
            )
        for product in self:
            self.env["ai.product.embedding"].index_product(product, provider)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Products indexed"),
                "message": _("%s product(s) indexed for RAG.") % len(self),
                "type": "success",
            },
        }

    def action_ai_clear_index(self):
        self.env["ai.product.embedding"].search(
            [("product_tmpl_id", "in", self.ids)]
        ).unlink()
        self.write({"ai_indexed": False, "ai_indexed_date": False})
