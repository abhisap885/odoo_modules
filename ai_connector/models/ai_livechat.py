from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class AILivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    ai_enabled = fields.Boolean(
        string="AI Auto-Reply",
        help="Let the AI answer visitor messages using your product knowledge (RAG).",
    )
    ai_provider_id = fields.Many2one(
        "ai.provider", string="AI Provider", help="Chat model used for replies."
    )
    ai_rag = fields.Boolean(string="Use Product Knowledge (RAG)", default=True)
    ai_rag_top_k = fields.Integer(string="Retrieved Chunks", default=3)
    ai_system_prompt = fields.Text(
        string="System Prompt",
        default=(
            "You are a helpful e-commerce assistant for our store. "
            "Answer using ONLY the provided product context when relevant. "
            "Cite the product name. If the answer is not in the context, "
            "give a polite general answer and suggest contacting our team."
        ),
    )
    ai_max_tokens = fields.Integer(default=512)
    ai_temperature = fields.Float(default=0.4)
    ai_fallback_general = fields.Boolean(
        string="Allow General Answers",
        default=True,
        help="If no product context is found, let the AI answer from general knowledge.",
    )


class MailChannel(models.Model):
    _inherit = "discuss.channel"

    def message_post(self, body="", message_type="notification", **kwargs):
        if self.env.context.get("ai_skip_hook"):
            return super().message_post(body=body, message_type=message_type, **kwargs)
        message = super().message_post(body=body, message_type=message_type, **kwargs)
        if not self.env.context.get("ai_no_respond"):
            self._ai_livechat_maybe_respond(message)
        return message

    # ------------------------------------------------------------------ #
    # AI auto-reply
    # ------------------------------------------------------------------ #
    def _ai_livechat_maybe_respond(self, message):
        self.ensure_one()
        if self.channel_type != "livechat":
            return
        channel = self.livechat_channel_id
        if not channel or not channel.ai_enabled:
            return
        if message.message_type != "comment" or not message.body:
            return

        operator_partner = self.livechat_operator_id.partner_id if self.livechat_operator_id else self.env.ref("base.partner_root", raise_if_not_found=False)
        visitor_partner = False
        if "livechat_visitor_id" in self._fields:
            visitor = self.livechat_visitor_id
            visitor_partner = visitor.partner_id if visitor else False

        author = message.author_id
        # Only react to visitor messages, never to the operator/bot's own messages.
        if operator_partner and author == operator_partner:
            return
        if visitor_partner and author != visitor_partner:
            return

        query = html2plaintext(message.body).strip()
        if not query:
            return

        try:
            answer = self._ai_generate_reply(channel, query)
        except Exception as exc:  # noqa: BLE001
            self.with_context(ai_skip_hook=True).message_post(
                body="AI is temporarily unavailable: %s" % exc,
                message_type="comment",
                author_id=operator_partner.id if operator_partner else None,
            )
            return

        self.with_context(ai_skip_hook=True).message_post(
            body=answer,
            message_type="comment",
            author_id=operator_partner.id if operator_partner else None,
        )

    def _ai_generate_reply(self, channel, query):
        provider = channel.ai_provider_id or self.env["ai.provider"]._get_default_provider()
        if not provider:
            raise UserError(_("No AI provider configured for this live chat channel."))

        system = channel.ai_system_prompt or ""
        if channel.ai_rag:
            emb_provider = self.env["ai.provider"].get_embedding_provider()
            if emb_provider:
                key = emb_provider._decrypt_key(emb_provider.api_key)
                q_vec = self.env["ai.product.embedding"]._embed_query(
                    emb_provider, key, query
                )
                top_chunks, score = self.env["ai.product.embedding"].search_similar(
                    q_vec, limit=channel.ai_rag_top_k
                )
                if top_chunks:
                    blocks = [
                        "• %s\n%s" % (c.product_tmpl_id.name or c.name, c.content)
                        for c in top_chunks
                    ]
                    context_text = "\n\n".join(blocks)
                    system += (
                        "\n\nUse the following product context to answer the "
                        "customer's question. Cite product names.\n\n%s" % context_text
                    )
                elif not channel.ai_fallback_general:
                    return (
                        "I couldn't find a matching product in our catalog. "
                        "A team member will follow up shortly."
                    )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]

        client = provider._get_client()
        reply = client.chat(
            messages, temperature=channel.ai_temperature, max_tokens=channel.ai_max_tokens
        )
        provider.action_increase_tokens(len(reply) // 4)
        return reply


class AIProductEmbedding(models.Model):
    _inherit = "ai.product.embedding"

    @api.model
    def _embed_query(self, provider, key, query):
        from ..utils.ai_client import get_embedding

        return get_embedding(
            provider.provider, key, provider.embedding_model, query, provider.base_url or None
        )


class AIProvider(models.Model):
    _inherit = "ai.provider"

    @api.model
    def _get_default_provider(self):
        company = self.env.company
        provider = self.search(
            [("company_id", "=", company.id), ("active", "=", True)], limit=1
        )
        if not provider:
            provider = self.search([("active", "=", True)], limit=1)
        return provider
