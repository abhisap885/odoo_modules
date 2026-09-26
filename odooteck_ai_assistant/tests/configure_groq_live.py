"""Configure the demo assistant's Groq provider from a key sent on stdin.

This helper never prints or stores the key in a source file. Run inside the Odoo
container and pipe the key through stdin; do not put it on the command line.
"""
import sys

sys.path.insert(0, "/opt/odoo")
import odoo  # noqa: E402
from odoo import api  # noqa: E402
from odoo.modules.registry import Registry  # noqa: E402
from odoo.tools import config  # noqa: E402

key = sys.stdin.readline().strip()
if not key.startswith("gsk_") or len(key) < 30:
    raise SystemExit("A valid Groq API key is required on stdin.")

config.parse_config(["-c", "/etc/odoo.conf", "-d", "demo"])
with Registry("demo").cursor() as cr:
    env = api.Environment(cr, api.SUPERUSER_ID, {})
    Provider = env["ot.ai.provider"].sudo()
    provider = Provider.search([("name", "=", "Groq Live")], limit=1)
    values = {
        "name": "Groq Live", "kind": "groq", "model_name": "openai/gpt-oss-20b",
        "api_key": key, "temperature": 0.2, "max_tokens": 350,
    }
    if provider:
        provider.write(values)
    else:
        provider = Provider.create(values)
    bot = env.ref("odooteck_ai_assistant.default_bot")
    bot.sudo().write({"provider_id": provider.id, "response_mode": "hybrid"})
    cr.commit()
print("Groq provider configured on demo; key was not printed.")
