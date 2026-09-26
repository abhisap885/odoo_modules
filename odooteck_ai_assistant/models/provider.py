import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OTAIProvider(models.Model):
    _name = "ot.ai.provider"
    _description = "AI Provider"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection([
        ("openai", "OpenAI"), ("groq", "Groq"),
        ("gemini", "Gemini"), ("compatible", "OpenAI compatible / local"),
    ], required=True, default="openai")
    endpoint = fields.Char(help="Only set for an OpenAI compatible or local endpoint. HTTPS is required except loopback.")
    api_key = fields.Char(groups="odooteck_ai_assistant.group_ai_manager", copy=False)
    model_name = fields.Char(required=True, default="gpt-4o-mini")
    temperature = fields.Float(default=0.2)
    max_tokens = fields.Integer(default=500)
    timeout_seconds = fields.Integer(default=20)
    input_cost_per_million = fields.Float(help="Optional cost estimate in USD per million input tokens")
    output_cost_per_million = fields.Float(help="Optional cost estimate in USD per million output tokens")

    def _endpoint(self):
        self.ensure_one()
        if self.kind == "openai":
            return "https://api.openai.com/v1/chat/completions"
        if self.kind == "groq":
            return "https://api.groq.com/openai/v1/chat/completions"
        if self.kind == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % self.model_name
        return (self.endpoint or "").strip()

    def _validate_endpoint(self, endpoint):
        parsed = urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValidationError(_("The provider endpoint must be an HTTP(S) URL without credentials."))
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValidationError(_("Use HTTPS for remote AI endpoints."))
        # Provider settings are manager-only, but prevent a remote endpoint from reaching private services.
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            try:
                addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
                if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                    raise ValidationError(_("Remote provider endpoints must resolve to public addresses."))
            except OSError as exc:
                raise ValidationError(_("Could not resolve provider endpoint: %s") % exc) from exc

    def request_completion(self, messages):
        self.ensure_one()
        endpoint = self._endpoint()
        self._validate_endpoint(endpoint)
        if not self.api_key and self.kind != "compatible":
            raise ValidationError(_("API key is missing for %s.") % self.name)
        timeout = max(3, min(self.timeout_seconds or 20, 60))
        if self.kind == "gemini":
            payload = {
                "contents": [{"role": "model" if m["role"] == "assistant" else "user",
                              "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"],
                "systemInstruction": {"parts": [{"text": next((m["content"] for m in messages if m["role"] == "system"), "")}]},
                "generationConfig": {"temperature": self.temperature, "maxOutputTokens": self.max_tokens},
            }
            headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        else:
            payload = {"model": self.model_name, "messages": messages,
                       "temperature": self.temperature, "max_tokens": self.max_tokens}
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = "Bearer %s" % self.api_key
        try:
            response = requests.post(endpoint, data=json.dumps(payload), headers=headers, timeout=timeout, allow_redirects=False)
            response.raise_for_status()
            data = response.json()
            if self.kind == "gemini":
                answer = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                usage = data.get("usageMetadata", {})
                prompt_tokens = int(usage.get("promptTokenCount", 0))
                completion_tokens = int(usage.get("candidatesTokenCount", 0))
            else:
                answer = data["choices"][0]["message"]["content"] or ""
                usage = data.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", 0))
                completion_tokens = int(usage.get("completion_tokens", 0))
            cost = (prompt_tokens * self.input_cost_per_million + completion_tokens * self.output_cost_per_million) / 1000000
            return answer.strip(), prompt_tokens, completion_tokens, cost
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            _logger.warning("AI provider %s failed: %s", self.id, exc)
            raise ValidationError(_("AI provider is temporarily unavailable.")) from exc
