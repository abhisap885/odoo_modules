"""Odoo shell test for the Live Chat message hook. All changes roll back."""

bot = env["ot.ai.bot"].create({"name": "Live Chat smoke bot", "website_enabled": False,
                                "allow_product_search": False})
env["ot.ai.knowledge"].create({"bot_id": bot.id, "name": "Shipping",
                                "question": "shipping information", "answer": "Shipping details are in the help center."})
livechat = env["im_livechat.channel"].create({"name": "AI Live Chat smoke", "ot_ai_bot_id": bot.id})
visitor = env["res.partner"].create({"name": "AI test visitor"})
channel = env["discuss.channel"].create({
    "name": "AI Live Chat session", "channel_type": "livechat",
    "livechat_channel_id": livechat.id, "livechat_operator_id": env.user.partner_id.id,
})
channel._add_members(partners=env.user.partner_id | visitor)
channel.sudo().message_post(body="shipping information", author_id=visitor.id,
                            message_type="comment", subtype_xmlid="mail.mt_comment")
assert channel.ot_ai_session_id and channel.ot_ai_session_id.source == "livechat"
assert channel.ot_ai_session_id.message_ids.filtered(lambda item: item.role == "assistant")
print("PASS: Live Chat visitor message created an assistant reply")
