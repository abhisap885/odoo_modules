"""Provider-agnostic AI client.

Wraps the HTTP APIs of the supported providers (OpenAI, Anthropic, Google Gemini,
Mistral and local Ollama) behind a single :meth:`AIClient.chat` interface so the
rest of the module does not need to care which vendor is configured.

Only the Python standard library plus Odoo's bundled ``requests`` are used, so no
extra dependency is required.
"""

import json
import logging

import requests

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"
PROVIDER_MISTRAL = "mistral"
PROVIDER_OLLAMA = "ollama"

#: Friendly model suggestions per provider (used in the UI).
DEFAULT_MODELS = {
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_ANTHROPIC: "claude-3-5-sonnet-latest",
    PROVIDER_GEMINI: "gemini-1.5-flash",
    PROVIDER_MISTRAL: "mistral-large-latest",
    PROVIDER_OLLAMA: "llama3.1",
}

#: Default embedding models per provider (used for RAG).
DEFAULT_EMBEDDING_MODELS = {
    PROVIDER_OPENAI: "text-embedding-3-small",
    PROVIDER_MISTRAL: "mistral-embed",
    PROVIDER_OLLAMA: "nomic-embed-text",
}

#: Providers that can produce vector embeddings via this client.
EMBEDDING_CAPABLE = (PROVIDER_OPENAI, PROVIDER_MISTRAL, PROVIDER_OLLAMA)


class AIClientError(Exception):
    """Raised when a provider call fails."""


class AIClient:
    """Thin wrapper that performs a single chat completion against a provider."""

    def __init__(self, provider, api_key, model, base_url=None, timeout=DEFAULT_TIMEOUT):
        self.provider = provider
        self.api_key = api_key
        self.model = model or DEFAULT_MODELS.get(provider, "")
        self.base_url = base_url
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def chat(self, messages, temperature=0.7, max_tokens=1024):
        """Send ``messages`` and return the assistant text.

        ``messages`` is a list of ``{"role": "user"/"assistant"/"system", "content": str}``.
        """
        handler = {
            PROVIDER_OPENAI: self._call_openai,
            PROVIDER_MISTRAL: self._call_openai,  # Mistral mirrors the OpenAI shape
            PROVIDER_ANTHROPIC: self._call_anthropic,
            PROVIDER_GEMINI: self._call_gemini,
            PROVIDER_OLLAMA: self._call_ollama,
        }.get(self.provider)
        if not handler:
            raise AIClientError("Unsupported provider: %s" % self.provider)
        return handler(messages, temperature, max_tokens)

    # ------------------------------------------------------------------ #
    # Provider implementations
    # ------------------------------------------------------------------ #
    def _call_openai(self, messages, temperature, max_tokens):
        url = (self.base_url or "https://api.openai.com/v1") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": "Bearer %s" % self.api_key,
                   "Content-Type": "application/json"}
        data = self._post(url, headers, payload)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("Unexpected OpenAI response: %s" % exc)

    def _call_mistral(self, messages, temperature, max_tokens):
        # Mistral's chat endpoint is OpenAI-compatible.
        return self._call_openai(messages, temperature, max_tokens)

    def _call_anthropic(self, messages, temperature, max_tokens):
        url = (self.base_url or "https://api.anthropic.com/v1") + "/messages"
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        chat_messages = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = self._post(url, headers, payload)
        try:
            return "".join(block.get("text", "") for block in data["content"]).strip()
        except (KeyError, TypeError) as exc:
            raise AIClientError("Unexpected Anthropic response: %s" % exc)

    def _call_gemini(self, messages, temperature, max_tokens):
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = "%s/models/%s:generateContent?key=%s" % (base, self.model, self.api_key)
        contents = []
        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = m["content"]
                continue
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        data = self._post(url, {"Content-Type": "application/json"}, payload, method="post_raw")
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("Unexpected Gemini response: %s" % exc)

    def _call_ollama(self, messages, temperature, max_tokens):
        url = (self.base_url or "http://localhost:11434") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        data = self._post(url, {"Content-Type": "application/json"}, payload)
        try:
            return data["message"]["content"].strip()
        except (KeyError, TypeError) as exc:
            raise AIClientError("Unexpected Ollama response: %s" % exc)

    # ------------------------------------------------------------------ #
    # HTTP helper
    # ------------------------------------------------------------------ #
    def _post(self, url, headers, payload, method="post_json"):
        try:
            if method == "post_raw":
                resp = requests.post(url, headers=headers, data=json.dumps(payload),
                                     timeout=self.timeout)
            else:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AIClientError("Network error: %s" % exc)
        if resp.status_code >= 400:
            raise AIClientError("HTTP %s: %s" % (resp.status_code, resp.text[:500]))
        try:
            return resp.json()
        except ValueError as exc:
            raise AIClientError("Invalid JSON response: %s" % exc)


# ---------------------------------------------------------------------- #
# Embeddings (used by the RAG / product knowledge engine)
# ---------------------------------------------------------------------- #
def get_embedding(provider, api_key, model, text, base_url=None, timeout=DEFAULT_TIMEOUT):
    """Return a single embedding vector (list[float]) for ``text``."""
    if not model:
        model = DEFAULT_EMBEDDING_MODELS.get(provider)
    if provider == PROVIDER_OLLAMA:
        url = (base_url or "http://localhost:11434") + "/api/embed"
        payload = {"model": model, "input": text}
        data = _post_raw(url, {}, payload, timeout)
        try:
            return data["embeddings"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("Unexpected Ollama embed response: %s" % exc)
    # OpenAI-compatible embeddings endpoint (OpenAI, Mistral, ...).
    url = (base_url or "https://api.openai.com/v1") + "/embeddings"
    payload = {"model": model, "input": text}
    headers = {"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"}
    data = _post_raw(url, headers, payload, timeout)
    try:
        return data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError("Unexpected embedding response: %s" % exc)


def _post_raw(url, headers, payload, timeout):
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise AIClientError("Network error: %s" % exc)
    if resp.status_code >= 400:
        raise AIClientError("HTTP %s: %s" % (resp.status_code, resp.text[:500]))
    try:
        return resp.json()
    except ValueError as exc:
        raise AIClientError("Invalid JSON response: %s" % exc)
