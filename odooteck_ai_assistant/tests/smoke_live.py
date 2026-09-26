"""Run through Odoo shell on a staging/demo database; shell rolls back changes.

Example:
  cat tests/smoke_live.py | python3 /opt/odoo/odoo-bin shell -c /etc/odoo.conf -d demo
"""
import base64

from odoo.exceptions import ValidationError


bot = env["ot.ai.bot"].create({
    "name": "Smoke test assistant", "website_enabled": False,
    "allow_product_search": False, "max_requests_per_minute": 2,
})
csv_data = b"name,question,answer,keywords\nShipping,How long is shipping?,Shipping takes three days,shipping\n"
wizard = env["ot.ai.knowledge.import"].create({
    "bot_id": bot.id, "filename": "facts.csv", "file": base64.b64encode(csv_data),
})
wizard.action_import()
assert env["ot.ai.knowledge"].retrieve(bot, "shipping time").name == "Shipping"

session = env["ot.ai.session"].create({"bot_id": bot.id, "source": "website"})
result = session.reply("How long is shipping?")
assert result["answer"] == "Shipping takes three days", result
env["ot.ai.message"].browse(result["message_id"]).set_feedback("positive")
assert session.message_ids.filtered(lambda item: item.feedback == "positive")

result = session.reply("unknown question")
assert "could not find" in result["answer"].lower(), result
session.action_summarize()
assert session.summary and session.action_download_summary()["type"] == "ir.actions.act_url"
try:
    session.reply("third message")
    raise AssertionError("Per-session rate limit did not fire")
except ValidationError:
    pass

shared_bot = env["ot.ai.bot"].create({
    "name": "Shared knowledge smoke bot", "website_enabled": False,
    "allow_product_search": False, "shared_knowledge_bot_ids": [(4, bot.id)],
})
shared_session = env["ot.ai.session"].create({"bot_id": shared_bot.id, "source": "website"})
assert shared_session.reply("shipping time")["answer"] == "Shipping takes three days"
handoff = shared_session.reply("human")
assert handoff["handoff"] and shared_session.state == "handoff"
lead = shared_session.capture_lead("Smoke Tester", "smoke@example.invalid", True)
assert lead and shared_session.lead_id == lead

channel = env["discuss.channel"].create({
    "name": "AI smoke channel", "channel_type": "channel", "ot_ai_bot_id": bot.id,
})
channel._add_members(partners=env.user.partner_id)
channel.message_post(body="How long is shipping?", message_type="comment", subtype_xmlid="mail.mt_comment")
assert channel.ot_ai_session_id, "Discuss did not create an AI session"
assert channel.ot_ai_session_id.message_ids.filtered(lambda item: item.role == "assistant")

print("PASS: knowledge import, grounded reply, feedback, summary export, fallback, rate limit, shared knowledge, handoff, lead and Discuss")
