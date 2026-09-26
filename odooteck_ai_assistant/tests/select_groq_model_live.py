"""Select a verified Groq model in the demo database. Run via Odoo shell."""
provider = env["ot.ai.provider"].sudo().search([("name", "=", "Groq Live")], limit=1)
assert provider and provider.kind == "groq"
provider.model_name = "openai/gpt-oss-20b"
env.cr.commit()
print("Verified Groq model selected.")
