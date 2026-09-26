import logging

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext, plaintext2html

_logger = logging.getLogger(__name__)


class OTLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    ot_ai_bot_id = fields.Many2one("ot.ai.bot", string="AI Assistant", help="Reply to visitor messages in this Live Chat channel.")


class OTDiscussChannel(models.Model):
    _inherit = "discuss.channel"

    ot_ai_bot_id = fields.Many2one("ot.ai.bot", string="AI Assistant")
    ot_ai_session_id = fields.Many2one("ot.ai.session", string="AI Session", readonly=True)

    def _message_post_after_hook(self, message, msg_vals):
        result = super()._message_post_after_hook(message, msg_vals)
        if self.env.context.get("ot_ai_reply") or len(self) != 1 or message.message_type != "comment":
            return result
        bot = self.ot_ai_bot_id or (self.livechat_channel_id.ot_ai_bot_id if self.livechat_channel_id else False)
        if not bot or not bot.active:
            return result
        source = "livechat" if self.livechat_channel_id else "discuss"
        if source == "livechat" and message.author_id and message.author_id == self.livechat_operator_id:
            return result
        partner = self.env.ref("odooteck_ai_assistant.partner_ai_assistant", raise_if_not_found=False)
        if partner and message.author_id == partner:
            return result
        query = html2plaintext(message.body or "").strip()
        if not query:
            return result
        response_text = False
        try:
            with self.env.cr.savepoint():
                session = self.sudo().ot_ai_session_id
                if not session:
                    session = self.env["ot.ai.session"].sudo().create({
                        "bot_id": bot.id, "channel_id": self.id, "source": source,
                        "name": self.name or "Chat",
                    })
                    self.sudo().ot_ai_session_id = session.id
                response_text = session.reply(query)["answer"]
        except ValidationError as exc:
            response_text = str(exc)
        except Exception:
            _logger.exception("AI reply failed for Discuss channel %s", self.id)
            response_text = bot.fallback_message or "The assistant is temporarily unavailable."
        if response_text:
            self.sudo().with_context(ot_ai_reply=True).message_post(
                body=plaintext2html(response_text), message_type="comment",
                author_id=partner.id if partner else False,
                subtype_xmlid="mail.mt_comment",
            )
        return result
