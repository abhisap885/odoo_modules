from odoo import _, fields, models
from odoo.exceptions import ValidationError
import json

class OTAIProductSync(models.TransientModel):
    _name = "ot.ai.product.sync"
    _description = "Sync Products to AI Knowledge"

    bot_id = fields.Many2one("ot.ai.bot", required=True)
    field_name = fields.Boolean(string="Include Name", default=True)
    field_description = fields.Boolean(string="Include Description", default=True)
    field_price = fields.Boolean(string="Include Price", default=True)
    
    def action_sync(self):
        self.ensure_one()
        provider = self.bot_id.provider_id
        products = self.env["product.template"].search([("website_published", "=", True), ("sale_ok", "=", True)])
        
        values = []
        for p in products:
            parts = []
            if self.field_name and p.name:
                parts.append(f"Product Name: {p.name}")
            if self.field_description and p.description_sale:
                parts.append(f"Description: {p.description_sale}")
            if self.field_price:
                parts.append(f"Price: {p.list_price} {p.currency_id.name}")
                
            content = "\n".join(parts)
            if not content:
                continue
                
            emb = "[]"
            if provider and provider.kind != 'groq':
                vector = provider.request_embedding(content)
                if vector:
                    emb = json.dumps(vector)
                    
            values.append({
                "bot_id": self.bot_id.id,
                "name": f"Product: {p.name}",
                "answer": content,
                "source_url": f"/shop/product/{p.id}",
                "embedding": emb,
                "keywords": p.name,
            })
            
        if values:
            self.env["ot.ai.knowledge"].search([("bot_id", "=", self.bot_id.id), ("name", "like", "Product:")]).unlink()
            self.env["ot.ai.knowledge"].create(values)
            
        return {"type": "ir.actions.act_window_close"}