import base64
import csv
import io
import json

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class OTAIKnowledgeImport(models.TransientModel):
    _name = "ot.ai.knowledge.import"
    _description = "Import AI Knowledge"

    bot_id = fields.Many2one("ot.ai.bot", required=True)
    file = fields.Binary(required=True)
    filename = fields.Char(required=True)

    def action_import(self):
        self.ensure_one()
        raw = base64.b64decode(self.file or "")
        if len(raw) > 2 * 1024 * 1024:
            raise ValidationError(_("Knowledge files must be 2 MB or smaller."))
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError(_("The file must use UTF-8 text.")) from exc
        filename = (self.filename or "").lower()
        if filename.endswith(".txt"):
            rows = [{"name": "%s (part %s)" % (self.filename, index + 1),
                     "answer": content[start:start + 10000]}
                    for index, start in enumerate(range(0, len(content), 10000))]
        elif filename.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(content)))
        elif filename.endswith(".json"):
            try:
                rows = json.loads(content)
            except ValueError as exc:
                raise ValidationError(_("Invalid JSON knowledge file.")) from exc
        else:
            raise ValidationError(_("Upload a .txt, .csv or .json file."))
        if not isinstance(rows, list) or not rows or len(rows) > 200:
            raise ValidationError(_("The file must contain between 1 and 200 knowledge entries."))
        values = []
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValidationError(_("Every knowledge entry must be an object or CSV row."))
            answer = str(row.get("answer") or "").strip()
            if not answer or len(answer) > 10000:
                raise ValidationError(_("Entry %s needs an answer under 10,000 characters.") % index)
            values.append({
                "bot_id": self.bot_id.id,
                "name": str(row.get("name") or row.get("question") or "Article %s" % index)[:150],
                "question": str(row.get("question") or "")[:250],
                "keywords": str(row.get("keywords") or "")[:500],
                "answer": answer,
                "source_url": str(row.get("source_url") or "")[:500],
            })
        self.env["ot.ai.knowledge"].create(values)
        return {"type": "ir.actions.act_window_close"}
