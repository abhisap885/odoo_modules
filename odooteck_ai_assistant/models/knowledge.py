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
    embedding = fields.Text(help="JSON encoded vector")

    @api.model
    def _terms(self, text):
        return set(re.findall(r"[\w]{3,}", (text or "").casefold()))

    
    @api.model
    def retrieve(self, bot, query, limit=3):
        provider = bot.provider_id
        if not provider or provider.kind == 'groq': 
            # Fallback to standard keyword search if no valid embedding provider
            return self._retrieve_keyword(bot, query, limit)
            
        query_emb = provider.request_embedding(query)
        if not query_emb:
            return self._retrieve_keyword(bot, query, limit)
            
        import json
        import math
        
        articles = self.sudo().search([
            ("bot_id", "in", (bot | bot.shared_knowledge_bot_ids).ids), ("active", "=", True),
            ("embedding", "!=", False)
        ], limit=500)
        
        ranked = []
        for article in articles:
            try:
                emb = json.loads(article.embedding)
                # Cosine similarity
                dot = sum(a * b for a, b in zip(query_emb, emb))
                norm_a = math.sqrt(sum(a * a for a in query_emb))
                norm_b = math.sqrt(sum(b * b for b in emb))
                score = dot / (norm_a * norm_b) if norm_a and norm_b else 0
                if score > 0.4: # Threshold
                    ranked.append((score, article.id))
            except Exception:
                continue
                
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return self.browse([article_id for _, article_id in ranked[:limit]])
        
    @api.model
    def _retrieve_keyword(self, bot, query, limit=3):

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
