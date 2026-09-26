import hashlib
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request


class OTAIChatController(http.Controller):
    def _session(self, token):
        if not isinstance(token, str) or len(token) > 128:
            return request.env["ot.ai.session"]
        return request.env["ot.ai.session"].sudo().search([
            ("access_token", "=", token), ("source", "=", "website")], limit=1)

    def _visitor_hash(self):
        value = "%s:%s" % (request.db or "", request.httprequest.remote_addr or "")
        return hashlib.sha256(value.encode()).hexdigest()

    @http.route("/ot_ai/chat/start", type="jsonrpc", auth="public", website=True)
    def start(self, token=None):
        session = self._session(token)
        if not session:
            bot = request.env["ot.ai.bot"].sudo().search([
                ("active", "=", True), ("website_enabled", "=", True)], limit=1)
            if not bot:
                return {"enabled": False}
            visitor_hash = self._visitor_hash()
            if request.env["ot.ai.session"].sudo().search_count([
                ("visitor_hash", "=", visitor_hash),
                ("create_date", ">=", fields.Datetime.now() - timedelta(minutes=1)),
            ]) >= 5:
                return {"enabled": False}
            session = request.env["ot.ai.session"].sudo().create({
                "bot_id": bot.id, "source": "website", "visitor_hash": visitor_hash,
            })
        messages = request.env["ot.ai.message"].sudo().search(
            [("session_id", "=", session.id)], order="id desc", limit=30)
        return {"enabled": True, "token": session.access_token, "bot_name": session.bot_id.name,
                "welcome": session.bot_id.welcome_message,
                "handoff": session.state == "handoff",
                "messages": [{"role": item.role, "body": item.body, "id": item.id,
                              "feedback": item.feedback or False} for item in reversed(messages)]}

    @http.route("/ot_ai/chat/send", type="jsonrpc", auth="public", website=True)
    def send(self, token=None, message=None):
        session = self._session(token)
        if not session:
            return {"error": _("Chat session expired. Please refresh the page.")}
        try:
            return session.reply(message)
        except ValidationError as exc:
            return {"error": str(exc)}

    @http.route("/ot_ai/chat/feedback", type="jsonrpc", auth="public", website=True)
    def feedback(self, token=None, message_id=None, value=None, note=""):
        session = self._session(token)
        if not session:
            return {"error": _("Chat session expired.")}
        message = request.env["ot.ai.message"].sudo().search([
            ("id", "=", int(message_id or 0)), ("session_id", "=", session.id),
        ], limit=1)
        if not message:
            return {"error": _("Message not found.")}
        try:
            message.set_feedback(value, note)
            return {"ok": True, "handoff": session.state == "handoff"}
        except ValidationError as exc:
            return {"error": str(exc)}

    @http.route("/ot_ai/chat/lead", type="jsonrpc", auth="public", website=True)
    def lead(self, token=None, name=None, email=None, consent=False):
        session = self._session(token)
        if not session:
            return {"error": _("Chat session expired.")}
        try:
            session.capture_lead(name, email, consent)
            return {"ok": True}
        except ValidationError as exc:
            return {"error": str(exc)}
