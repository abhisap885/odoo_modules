from odoo import http
from odoo.http import request, route
import json


class AIConnectorController(http.Controller):
    """JSON endpoints used by the frontend chat widget."""

    @route("/ai_connector/chat", type="json", auth="user", methods=["POST"])
    def chat(self, chat_id=None, message=None, provider_id=None, **kwargs):
        if not message:
            return {"error": "Empty message."}
        chat = None
        if chat_id:
            chat = request.env["ai.chat"].browse(int(chat_id)).exists()
        if not chat:
            chat = request.env["ai.chat"].create({"name": message[:60]})
        if provider_id:
            chat.provider_id = int(provider_id)
        try:
            reply = chat.action_ask(message)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"chat_id": chat.id, "reply": reply}

    @route("/ai_connector/providers", type="json", auth="user", methods=["POST"])
    def providers(self):
        providers = request.env["ai.provider"].search_read(
            [("active", "=", True)],
            ["id", "name", "provider", "model"],
        )
        return providers
