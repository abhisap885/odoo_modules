"""Run in Odoo shell; prints only HTTP status and provider error details."""
import requests

provider = env["ot.ai.provider"].sudo().search([("name", "=", "Groq Live")], limit=1)
assert provider
headers = {"Authorization": "Bearer %s" % provider.api_key}
for label, response in [
    ("models", requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=15)),
    ("chat", requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers,
                          json={"model": "openai/gpt-oss-20b",
                                "messages": [{"role": "user", "content": "Say hello."}],
                                "max_tokens": 20}, timeout=15)),
]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    details = data.get("error", {}) if isinstance(data, dict) else {}
    if label == "models" and isinstance(data, dict):
        print("available model IDs:", [item.get("id") for item in data.get("data", [])][:30])
    print(label, response.status_code, {
        "type": details.get("type"), "code": details.get("code"),
        "message": str(details.get("message", ""))[:300],
    })
