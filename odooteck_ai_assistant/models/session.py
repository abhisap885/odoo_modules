import base64
import logging
import re
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OTAISession(models.Model):
    _name = "ot.ai.session"
    _description = "AI Chat Session"
    _order = "create_date desc"

    name = fields.Char(default="New chat", required=True)
    access_token = fields.Char(default=lambda self: secrets.token_urlsafe(32), required=True, copy=False, index=True)
    visitor_hash = fields.Char(index=True, copy=False, help="Pseudonymous rate-limit key for website visitors")
    bot_id = fields.Many2one("ot.ai.bot", required=True, ondelete="restrict")
    channel_id = fields.Many2one("discuss.channel", ondelete="set null")
    source = fields.Selection([("website", "Website"), ("livechat", "Live Chat"), ("discuss", "Discuss")], required=True, default="website")
    state = fields.Selection([("open", "Open"), ("handoff", "Human requested"), ("closed", "Closed")], default="open", required=True)
    message_ids = fields.One2many("ot.ai.message", "session_id")
    message_count = fields.Integer(compute="_compute_message_count")
    lead_id = fields.Many2one("crm.lead", readonly=True)
    visitor_name = fields.Char()
    visitor_email = fields.Char()
    summary = fields.Text(readonly=True)
    last_activity = fields.Datetime(default=fields.Datetime.now)

    _access_token_unique = models.Constraint("UNIQUE(access_token)", "Chat access token must be unique.")

    @api.depends("message_ids")
    def _compute_message_count(self):
        for session in self:
            session.message_count = len(session.message_ids)

    def _products_for(self, query):
        self.ensure_one()
        if not self.bot_id.allow_product_search or self.source == "discuss":
            return []
        terms = self.env["ot.ai.knowledge"]._terms(query)
        if not terms:
            return []
        products = self.env["product.template"].sudo().search([
            ("website_published", "=", True), ("sale_ok", "=", True),
            ("name", "ilike", max(terms, key=len)),
        ], limit=5)
        if self.source == "website":
            website = self.env["website"].get_current_website()
            products = products.filtered(lambda product: not product.website_id or product.website_id == website)
        result = []
        for product in products:
            if terms & self.env["ot.ai.knowledge"]._terms(product.name):
                result.append({"name": product.name, "url": "/shop/product/%s" % product.id})
        return result[:3]

    def _context(self, query):
        articles = self.env["ot.ai.knowledge"].retrieve(self.bot_id, query)
        products = self._products_for(query)
        lines = []
        sources = []
        for article in articles:
            lines.append("Article: %s\n%s" % (article.name, (article.answer or "")[:1800]))
            if article.source_url and article.source_url.startswith(("https://", "http://")):
                sources.append({"label": article.name, "url": article.source_url})
        for product in products:
            lines.append("Published product: %(name)s; URL %(url)s" % product)
            sources.append({"label": product["name"], "url": product["url"]})
        return "\n\n".join(lines)[:6500], sources

    def _redact(self, text):
        if not self.bot_id.redact_pii:
            return text
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[email redacted]", text)
        return re.sub(r"(?<!\d)(?:\+?\d[\d .()-]{8,}\d)(?!\d)", "[phone redacted]", text)

    def _recent_history(self):
        limit = max(0, min(self.bot_id.max_history_turns, 12)) * 2
        if not limit:
            return []
        messages = self.env["ot.ai.message"].sudo().search(
            [("session_id", "=", self.id), ("role", "in", ["user", "assistant"])],
            order="id desc", limit=limit + 1)
        if messages and messages[0].role == "user":
            messages = messages[1:]
        messages = messages[:limit]
        return [{"role": "user" if item.role == "user" else "assistant", "content": item.body[:2000]}
                for item in reversed(messages)]

    def _local_answer(self, query, context, sources):
        articles = self.env["ot.ai.knowledge"].retrieve(self.bot_id, query, limit=1)
        if articles:
            return articles[0].answer[:2500]
        products = self._products_for(query)
        if products:
            return "I found these products: " + "; ".join(p["name"] for p in products)
        return self.bot_id.fallback_message

    def _call_ai(self, query, context):
        bot = self.bot_id
        if bot.response_mode == "grounded" and not context:
            return None
        if bot.response_mode == "general" or context:
            system = (bot.system_prompt or "")[:2000]
            if bot.response_mode != "general":
                system += "\nUse only these approved facts. If insufficient, say you do not know.\n" + context
            messages = [{"role": "system", "content": system}] + self._recent_history()
            messages.append({"role": "user", "content": query})
            for provider in (bot.provider_id, bot.fallback_provider_id):
                if not provider or not provider.active:
                    continue
                try:
                    answer, prompt_tokens, completion_tokens, cost = provider.sudo().request_completion(messages)
                    if answer:
                        return answer, prompt_tokens, completion_tokens, cost, provider
                except ValidationError:
                    _logger.info("Provider %s unavailable; trying fallback", provider.id)
        return None

    def _request_human(self):
        self.ensure_one()
        self.sudo().write({"state": "handoff", "last_activity": fields.Datetime.now()})
        if self.channel_id and self.source == "livechat":
            try:
                self.channel_id.sudo()._forward_human_operator()
            except Exception:
                _logger.exception("Could not forward live chat %s", self.channel_id.id)
        return _("A human agent has been requested. Please leave your name and email so the team can follow up.")

    def reply(self, query):
        self.ensure_one()
        query = (query or "").strip()
        if not query or len(query) > 2000:
            raise ValidationError(_("Please enter a message under 2,000 characters."))
        if self.state != "open":
            return {"answer": _("This chat has been handed to a human. Please leave your contact details."), "sources": [], "handoff": True}
        bot = self.bot_id.sudo()
        since = fields.Datetime.now() - timedelta(minutes=1)
        if bot.max_requests_per_minute and self.env["ot.ai.message"].sudo().search_count([
            ("session_id", "=", self.id), ("role", "=", "user"), ("create_date", ">=", since),
        ]) >= bot.max_requests_per_minute:
            raise ValidationError(_("Too many messages. Please wait a minute and try again."))
        if self.visitor_hash and self.env["ot.ai.message"].sudo().search_count([
            ("session_id.visitor_hash", "=", self.visitor_hash), ("role", "=", "user"),
            ("create_date", ">=", since),
        ]) >= 30:
            raise ValidationError(_("Too many messages from this visitor. Please wait a minute."))
        self.env["ot.ai.message"].sudo().create({"session_id": self.id, "bot_id": bot.id, "role": "user", "body": query})
        self.sudo().last_activity = fields.Datetime.now()
        if self.name == "New chat":
            self.sudo().name = query[:80]
        if bot.wants_human(query):
            answer = self._request_human()
            sources = []
            result = None
        else:
            context, sources = self._context(query)
            if not bot._budget_available():
                answer = _("The assistant has reached its daily usage limit. Please request a human agent.")
                result = None
            else:
                result = self._call_ai(query, context)
                answer = result[0] if result else self._local_answer(query, context, sources)
        answer = self._redact(answer or bot.fallback_message)
        message = self.env["ot.ai.message"].sudo().create({
            "session_id": self.id, "bot_id": bot.id, "role": "assistant", "body": answer,
            "provider_id": result[4].id if result else False,
            "prompt_tokens": result[1] if result else 0,
            "completion_tokens": result[2] if result else 0,
            "total_tokens": result[1] + result[2] if result else 0,
            "cost_usd": result[3] if result else 0,
        })
        return {"answer": answer, "sources": sources, "handoff": self.state == "handoff", "message_id": message.id}

    def capture_lead(self, name, email, consent):
        self.ensure_one()
        name, email = (name or "").strip()[:100], (email or "").strip()[:254]
        if not consent or not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValidationError(_("Enter a valid name and email, and consent to follow up."))
        if self.lead_id:
            return self.lead_id
        if self.visitor_hash and self.sudo().search_count([
            ("visitor_hash", "=", self.visitor_hash), ("lead_id", "!=", False),
            ("create_date", ">=", str(fields.Date.context_today(self))),
        ]) >= 3:
            raise ValidationError(_("Follow-up request limit reached for today."))
        lead = self.env["crm.lead"].sudo().create({
            "name": _("AI chat follow-up: %s") % self.name[:100],
            "contact_name": name, "email_from": email, "type": "lead",
            "description": _("Visitor requested follow-up from AI chat session #%s.") % self.id,
        })
        self.sudo().write({"lead_id": lead.id, "visitor_name": name, "visitor_email": email, "state": "handoff"})
        return lead

    def action_summarize(self):
        for session in self:
            transcript = "\n".join("%s: %s" % (m.role, m.body[:400]) for m in session.message_ids.sorted("id")[-30:])
            if not transcript:
                continue
            provider = session.bot_id.provider_id
            if provider:
                try:
                    text, _pt, _ct, _cost = provider.sudo().request_completion([
                        {"role": "system", "content": "Summarize this customer conversation in 5 factual bullet points. Do not invent facts."},
                        {"role": "user", "content": transcript[:8000]},
                    ])
                    session.summary = text
                    continue
                except ValidationError:
                    pass
            session.summary = transcript[:2000]

    def action_download_summary(self):
        self.ensure_one()
        if not self.summary:
            self.action_summarize()
        attachment = self.env["ir.attachment"].create({
            "name": "ai_chat_summary_%s.txt" % self.id,
            "type": "binary", "mimetype": "text/plain",
            "datas": base64.b64encode((self.summary or "").encode()),
            "res_model": self._name, "res_id": self.id,
        })
        return {"type": "ir.actions.act_url", "url": "/web/content/%s?download=true" % attachment.id,
                "target": "self"}


class OTAIMessage(models.Model):
    _name = "ot.ai.message"
    _description = "AI Chat Message"
    _order = "id"

    session_id = fields.Many2one("ot.ai.session", required=True, ondelete="cascade", index=True)
    bot_id = fields.Many2one("ot.ai.bot", required=True, ondelete="restrict", index=True)
    role = fields.Selection([("user", "Visitor"), ("assistant", "Assistant"), ("human", "Human")], required=True)
    body = fields.Text(required=True)
    provider_id = fields.Many2one("ot.ai.provider", readonly=True)
    prompt_tokens = fields.Integer(readonly=True)
    completion_tokens = fields.Integer(readonly=True)
    total_tokens = fields.Integer(readonly=True)
    cost_usd = fields.Float(readonly=True)
    feedback = fields.Selection([("positive", "Helpful"), ("negative", "Not helpful")])
    feedback_note = fields.Char()

    def set_feedback(self, feedback, note=""):
        self.ensure_one()
        if self.role != "assistant" or feedback not in ("positive", "negative"):
            raise ValidationError(_("Feedback can only be left on assistant replies."))
        self.sudo().write({"feedback": feedback, "feedback_note": (note or "")[:500]})
        session = self.session_id.sudo()
        if feedback == "negative" and session.bot_id.auto_handoff_after_negative:
            negatives = self.sudo().search_count([
                ("session_id", "=", session.id), ("feedback", "=", "negative")])
            if negatives >= session.bot_id.auto_handoff_after_negative and session.state == "open":
                session._request_human()
