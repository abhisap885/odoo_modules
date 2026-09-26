import re

from odoo import api, fields, models


class OTAIKnowledge(models.Model):
    _name = "ot.ai.knowledge"
    _description = "AI Knowledge Article"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    bot_id = fields.Many2one("ot.ai.bot", ondelete="cascade", required=True)
    question = fields.Char(help="Optional common customer question")
    answer = fields.Text(required=True, help="Approved answer and facts shown to the assistant")
    source_url = fields.Char(help="Optional public source URL to show shoppers")
    keywords = fields.Char(help="Comma separated search terms")

    @api.model
    def _terms(self, text):
        return set(re.findall(r"[\w]{3,}", (text or "").casefold()))

    @api.model
    def retrieve(self, bot, query, limit=3):
        terms = self._terms(query)
        if not terms:
            return self.browse()
        articles = self.sudo().search([
            ("bot_id", "in", (bot | bot.shared_knowledge_bot_ids).ids), ("active", "=", True),
        ], limit=300)
        ranked = []
        for article in articles:
            title_terms = self._terms(" ".join([article.name or "", article.question or "", article.keywords or ""]))
            body_terms = self._terms(article.answer)
            score = 3 * len(terms & title_terms) + len(terms & body_terms)
            if score:
                ranked.append((score, article.id))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return self.browse([article_id for _, article_id in ranked[:limit]])
