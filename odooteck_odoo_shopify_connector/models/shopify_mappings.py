# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ShopifyTemplateMapping(models.Model):
    _name = "shopify.template.mapping"
    _description = "Shopify Product Template Mapping"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    template_id = fields.Many2one("product.template", string="Odoo Product Template", required=True, ondelete="cascade")
    shopify_product_id = fields.Char(string="Shopify Product ID", required=True, index=True)
    shopify_handle = fields.Char(string="Shopify URL Handle")
    default_code = fields.Char(related="template_id.default_code", string="Internal Reference", readonly=True)
    list_price = fields.Float(related="template_id.list_price", string="Sales Price", readonly=True)
    variant_mapping_ids = fields.One2many("shopify.product.mapping", "template_mapping_id", string="Variant Mappings")

    shopify_status = fields.Selection(
        selection=[
            ("active", "Active on Shopify"),
            ("archived", "Archived on Shopify"),
            ("draft", "Draft on Shopify"),
            ("deleted", "Deleted on Shopify"),
        ],
        string="Shopify Status",
        default="active",
        index=True,
    )
    is_deleted_on_shopify = fields.Boolean(
        string="Deleted on Shopify",
        default=False,
        index=True,
        help="Indicates whether this product was removed or deleted from the Shopify store."
    )

    _instance_shopify_product_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_product_id)",
        "The Shopify Product ID must be unique per store!"
    )
    _instance_template_uniq = models.Constraint(
        "UNIQUE(instance_id, template_id)",
        "The Odoo Template is already mapped to this Shopify store!"
    )

    @api.depends("template_id", "template_id.name", "shopify_handle", "shopify_product_id")
    def _compute_display_name(self):
        for rec in self:
            title = rec.template_id.display_name or rec.template_id.name or rec.shopify_handle or (f"Shopify Product #{rec.shopify_product_id}" if rec.shopify_product_id else f"Product Mapping #{rec.id}")
            rec.display_name = title
            rec.name = title

    def action_odoo_to_shopify(self):
        """Update this product on Shopify with latest Odoo details."""
        self.ensure_one()
        return self.instance_id._update_product_to_shopify(self)

    def action_shopify_to_odoo(self):
        """Pull latest product details from Shopify to Odoo."""
        self.ensure_one()
        return self.instance_id._update_product_from_shopify(self)

    def action_check_shopify_status(self):
        """Verify if this product still exists on Shopify and update status."""
        self.ensure_one()
        return self.instance_id._check_shopify_product_status(self)


class ShopifyProductMapping(models.Model):
    _name = "shopify.product.mapping"
    _description = "Shopify Product Variant Mapping"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    template_mapping_id = fields.Many2one("shopify.template.mapping", string="Parent Template Mapping", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Odoo Product Variant", required=True, ondelete="cascade")
    shopify_variant_id = fields.Char(string="Shopify Variant ID", required=True, index=True)
    shopify_sku = fields.Char(string="Shopify SKU", index=True)
    shopify_inventory_item_id = fields.Char(string="Shopify Inventory Item ID", index=True)
    barcode = fields.Char(related="product_id.barcode", string="Barcode", readonly=True)
    qty_available = fields.Float(related="product_id.qty_available", string="On Hand Quantity", readonly=True)
    is_deleted_on_shopify = fields.Boolean(related="template_mapping_id.is_deleted_on_shopify", string="Deleted on Shopify", readonly=True)

    _instance_shopify_variant_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_variant_id)",
        "The Shopify Variant ID must be unique per store!"
    )
    _instance_product_uniq = models.Constraint(
        "UNIQUE(instance_id, product_id)",
        "The Odoo Product Variant is already mapped to this Shopify store!"
    )

    @api.depends("product_id", "product_id.name", "shopify_sku", "shopify_variant_id")
    def _compute_display_name(self):
        for rec in self:
            variant_title = rec.product_id.display_name or rec.product_id.name or (f"SKU: {rec.shopify_sku}" if rec.shopify_sku else f"Variant #{rec.shopify_variant_id or rec.id}")
            rec.display_name = variant_title
            rec.name = variant_title


class ShopifyOrderMapping(models.Model):
    _name = "shopify.order.mapping"
    _description = "Shopify Sales Order Mapping"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    order_id = fields.Many2one("sale.order", string="Odoo Sales Order", required=True, ondelete="cascade")
    shopify_order_id = fields.Char(string="Shopify Order ID", required=True, index=True)
    shopify_order_number = fields.Char(string="Shopify Order #", required=True, index=True)
    financial_status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
            ("partially_refunded", "Partially Refunded"),
            ("refunded", "Refunded"),
            ("voided", "Voided"),
        ],
        string="Financial Status",
    )
    fulfillment_status = fields.Selection(
        selection=[
            ("unfulfilled", "Unfulfilled"),
            ("partial", "Partially Fulfilled"),
            ("fulfilled", "Fulfilled"),
            ("restocked", "Restocked"),
        ],
        string="Fulfillment Status",
        default="unfulfilled",
    )
    partner_id = fields.Many2one(related="order_id.partner_id", string="Customer", readonly=True)
    amount_total = fields.Monetary(related="order_id.amount_total", currency_field="currency_id", string="Total Amount", readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id", string="Currency", readonly=True)

    _instance_shopify_order_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_order_id)",
        "The Shopify Order ID must be unique per store!"
    )
    _instance_order_uniq = models.Constraint(
        "UNIQUE(instance_id, order_id)",
        "The Odoo Order is already mapped to this Shopify store!"
    )

    @api.depends("shopify_order_number", "shopify_order_id", "order_id", "order_id.name")
    def _compute_display_name(self):
        for rec in self:
            ord_num = rec.shopify_order_number or rec.shopify_order_id or str(rec.id)
            if rec.order_id and rec.order_id.name:
                title = f"Shopify Order {ord_num} ({rec.order_id.name})"
            else:
                title = f"Shopify Order {ord_num}"
            rec.display_name = title
            rec.name = title


class ShopifyPartnerMapping(models.Model):
    _name = "shopify.partner.mapping"
    _description = "Shopify Customer Mapping"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Odoo Partner", required=True, ondelete="cascade")
    shopify_customer_id = fields.Char(string="Shopify Customer ID", required=True, index=True)
    email = fields.Char(string="Customer Email")
    phone = fields.Char(string="Customer Phone")

    _instance_shopify_customer_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_customer_id)",
        "The Shopify Customer ID must be unique per store!"
    )
    _instance_partner_uniq = models.Constraint(
        "UNIQUE(instance_id, partner_id)",
        "The Odoo Partner is already mapped to this Shopify store!"
    )

    @api.depends("partner_id", "partner_id.name", "email", "shopify_customer_id")
    def _compute_display_name(self):
        for rec in self:
            cust_name = rec.partner_id.display_name or rec.partner_id.name or rec.email or (f"Customer #{rec.shopify_customer_id}" if rec.shopify_customer_id else f"Customer #{rec.id}")
            rec.display_name = cust_name
            rec.name = cust_name


class ShopifyTaxMapping(models.Model):
    _name = "shopify.tax.mapping"
    _description = "Shopify Tax Rate Mapping"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    tax_id = fields.Many2one("account.tax", string="Odoo Tax", required=True)
    shopify_tax_title = fields.Char(string="Shopify Tax Title", required=True)
    rate = fields.Float(string="Tax Rate (%)")

    _instance_shopify_tax_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_tax_title)",
        "The Shopify Tax Title must be unique per store!"
    )

    @api.depends("shopify_tax_title", "tax_id", "tax_id.name", "rate")
    def _compute_display_name(self):
        for rec in self:
            if rec.tax_id and rec.tax_id.name:
                title = f"{rec.shopify_tax_title or 'Tax'} ({rec.tax_id.name})"
            elif rec.shopify_tax_title:
                title = f"{rec.shopify_tax_title} ({rec.rate}%)"
            else:
                title = f"Tax Mapping #{rec.id}"
            rec.display_name = title
            rec.name = title


class ShopifyLocationMapping(models.Model):
    _name = "shopify.location.mapping"
    _description = "Shopify Location Stock Mapping"
    _order = "is_primary desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="instance_id.company_id", string="Company", store=True, readonly=True)
    shopify_location_id = fields.Char(string="Shopify Location ID", required=True, index=True)
    shopify_location_name = fields.Char(string="Shopify Location Name", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Odoo Warehouse", domain="[('company_id', '=', company_id)]")
    location_id = fields.Many2one("stock.location", string="Odoo Stock Location", required=True, domain="[('company_id', 'in', (company_id, False)), ('usage', '=', 'internal')]")
    sync_stock = fields.Boolean(string="Sync Stock", default=True, help="Enable automatic inventory export/import for this location.")
    is_primary = fields.Boolean(string="Primary Location", default=False)
    active = fields.Boolean(string="Active", default=True)

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        if self.warehouse_id and self.warehouse_id.lot_stock_id:
            self.location_id = self.warehouse_id.lot_stock_id

    _instance_shopify_loc_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_location_id)",
        "The Shopify Location ID must be unique per store!"
    )

    @api.depends("shopify_location_name", "shopify_location_id", "warehouse_id", "warehouse_id.name")
    def _compute_display_name(self):
        for rec in self:
            loc_label = rec.shopify_location_name or f"Location #{rec.shopify_location_id or rec.id}"
            if rec.warehouse_id and rec.warehouse_id.name:
                title = f"{loc_label} [{rec.warehouse_id.name}]"
            else:
                title = loc_label
            rec.display_name = title
            rec.name = title


class ShopifyMetafieldMapping(models.Model):
    _name = "shopify.metafield.mapping"
    _description = "Shopify Metafield Field Mapping"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(string="Mapping Name", compute="_compute_name", store=True)
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    model_id = fields.Many2one(
        "ir.model",
        string="Applies To",
        required=True,
        domain="[('model', 'in', ['product.template', 'product.product', 'res.partner', 'sale.order'])]",
        ondelete="cascade",
    )
    model_name = fields.Char(related="model_id.model", string="Model Technical Name", readonly=True)
    store_type = fields.Selection(
        selection=[
            ("field", "Odoo Field"),
            ("custom", "Product Sheet Value"),
        ],
        string="Mapping Type",
        default="field",
        required=True,
        help="Odoo Field maps the Shopify metafield to a real Odoo field. Product Sheet Value stores editable values on product/template records.",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Odoo Field",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'boolean', 'selection', 'date', 'datetime'])]",
        ondelete="cascade",
    )
    namespace = fields.Char(string="Shopify Namespace", default="custom", required=True)
    key = fields.Char(string="Shopify Key", required=True)
    shopify_definition_id = fields.Char(string="Shopify Definition ID", readonly=True, copy=False)
    shopify_owner_type = fields.Selection(
        selection=[
            ("PRODUCT", "Product"),
            ("PRODUCTVARIANT", "Product Variant"),
            ("CUSTOMER", "Customer"),
            ("ORDER", "Order"),
        ],
        string="Shopify Owner Type",
        readonly=True,
        copy=False,
    )
    description = fields.Text(string="Description", readonly=True, copy=False)
    metafield_type = fields.Selection(
        selection=[
            ("single_line_text_field", "Single Line Text"),
            ("multi_line_text_field", "Multi-Line Text"),
            ("number_integer", "Integer"),
            ("number_decimal", "Decimal"),
            ("boolean", "Boolean"),
            ("json", "JSON"),
            ("url", "URL"),
        ],
        string="Shopify Metafield Type",
        default="single_line_text_field",
        required=True,
    )
    sync_direction = fields.Selection(
        selection=[
            ("both", "Bidirectional (Import & Export)"),
            ("import", "Import Only (Shopify -> Odoo)"),
            ("export", "Export Only (Odoo -> Shopify)"),
        ],
        string="Sync Direction",
        default="both",
        required=True,
    )
    active = fields.Boolean(string="Active", default=True)

    _instance_metafield_uniq = models.Constraint(
        "UNIQUE(instance_id, model_id, namespace, key)",
        "The combination of Model, Namespace, and Key must be unique per store!"
    )

    @api.depends("namespace", "key", "model_id", "model_id.name", "model_name")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.namespace or 'custom'}.{rec.key or 'metafield'} ({rec.model_id.name or rec.model_name or ''})"

    @api.depends("name", "namespace", "key", "model_id", "model_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or f"{rec.namespace or 'custom'}.{rec.key or 'metafield'}"

    @api.onchange("store_type")
    def _onchange_store_type(self):
        for rec in self:
            if rec.store_type == "custom":
                rec.field_id = False

    @api.constrains("store_type", "field_id", "model_id", "shopify_definition_id")
    def _check_store_type_scope(self):
        for rec in self:
            if rec.store_type == "field" and not rec.field_id and not rec.shopify_definition_id:
                raise ValidationError(_("Odoo Field is required when Mapping Type is Odoo Field."))
            if rec.store_type == "custom" and rec.field_id:
                raise ValidationError(_("Odoo Field must be empty when Mapping Type is Custom Value."))
            if rec.store_type == "custom" and rec.model_name not in ("product.template", "product.product"):
                raise ValidationError(_("Product Sheet Value metafields are supported for Products and Variants only."))


class ShopifyMetafieldValue(models.Model):
    _name = "shopify.metafield.value"
    _description = "Shopify Product Metafield Value"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    mapping_id = fields.Many2one("shopify.metafield.mapping", string="Metafield Mapping", required=True, ondelete="cascade")
    product_tmpl_id = fields.Many2one("product.template", string="Product Template", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product Variant", ondelete="cascade")
    namespace = fields.Char(related="mapping_id.namespace", string="Namespace", readonly=True)
    key = fields.Char(related="mapping_id.key", string="Key", readonly=True)
    metafield_type = fields.Selection(related="mapping_id.metafield_type", string="Metafield Type", readonly=True)
    model_name = fields.Char(related="mapping_id.model_name", string="Model", readonly=True)
    value = fields.Text(string="Value")

    _template_value_uniq = models.Constraint(
        "UNIQUE(instance_id, mapping_id, product_tmpl_id)",
        "This template metafield value already exists for this store and mapping!"
    )
    _variant_value_uniq = models.Constraint(
        "UNIQUE(instance_id, mapping_id, product_id)",
        "This variant metafield value already exists for this store and mapping!"
    )

    @api.depends("mapping_id", "mapping_id.key", "mapping_id.name", "value", "product_tmpl_id", "product_tmpl_id.name", "product_id", "product_id.name")
    def _compute_display_name(self):
        for rec in self:
            target = rec.product_tmpl_id.name or rec.product_id.display_name or ""
            key_label = rec.mapping_id.key or "Metafield"
            val_preview = (rec.value[:30] + "...") if rec.value and len(rec.value) > 30 else (rec.value or "")
            if target:
                title = f"{key_label}: {val_preview} ({target})" if val_preview else f"{key_label} ({target})"
            else:
                title = f"{key_label}: {val_preview}" if val_preview else f"Metafield Value #{rec.id}"
            rec.display_name = title
            rec.name = title

    @api.constrains("mapping_id", "product_tmpl_id", "product_id")
    def _check_target(self):
        for rec in self:
            if bool(rec.product_tmpl_id) == bool(rec.product_id):
                raise ValidationError(_("Set exactly one target: Product Template or Product Variant."))
            if rec.mapping_id.model_name == "product.template" and not rec.product_tmpl_id:
                raise ValidationError(_("Product Template is required for template metafields."))
            if rec.mapping_id.model_name == "product.product" and not rec.product_id:
                raise ValidationError(_("Product Variant is required for variant metafields."))


class ShopifyRefundMapping(models.Model):
    _name = "shopify.refund.mapping"
    _description = "Shopify Order Refund Mapping"
    _order = "date_refund desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    shopify_refund_id = fields.Char(string="Shopify Refund ID", required=True, index=True)
    shopify_order_id = fields.Char(string="Shopify Order ID", required=True, index=True)
    shopify_order_number = fields.Char(string="Shopify Order #", index=True)
    order_id = fields.Many2one("sale.order", string="Odoo Sales Order", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="order_id.partner_id", string="Customer", readonly=True)
    credit_note_id = fields.Many2one("account.move", string="Customer Credit Note", readonly=True)
    return_picking_id = fields.Many2one("stock.picking", string="Return Stock Transfer", readonly=True)
    amount = fields.Monetary(string="Refund Amount", currency_field="currency_id")
    currency_id = fields.Many2one(related="order_id.currency_id", string="Currency", readonly=True)
    reason = fields.Char(string="Refund Note / Reason")
    date_refund = fields.Datetime(string="Refund Date")
    state = fields.Selection(
        selection=[
            ("draft", "Pending"),
            ("processed", "Processed"),
            ("error", "Failed"),
        ],
        string="Status",
        default="draft",
        required=True,
        index=True,
    )
    error_message = fields.Text(string="Error Details")

    _instance_refund_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_refund_id)",
        "The Shopify Refund ID must be unique per store!"
    )

    @api.depends("shopify_refund_id", "shopify_order_number", "order_id", "order_id.name")
    def _compute_display_name(self):
        for rec in self:
            ord_label = rec.shopify_order_number or (rec.order_id.name if rec.order_id else "")
            if ord_label:
                title = f"Refund #{rec.shopify_refund_id or rec.id} (Order {ord_label})"
            else:
                title = f"Refund #{rec.shopify_refund_id or rec.id}"
            rec.display_name = title
            rec.name = title

    def action_process_refund(self):
        """Processes the refund by generating Credit Notes and updating financial status."""
        for rec in self:
            if rec.state == "processed":
                continue
            try:
                # 1. Generate Credit Note
                if not rec.credit_note_id and rec.instance_id.auto_create_credit_notes:
                    rec._create_credit_note()

                # 2. Update Order Financial Status
                order_map = self.env["shopify.order.mapping"].search([
                    ("instance_id", "=", rec.instance_id.id),
                    ("shopify_order_id", "=", rec.shopify_order_id),
                ], limit=1)
                if order_map:
                    order_map.financial_status = "refunded" if rec.amount >= order_map.amount_total else "partially_refunded"

                rec.write({"state": "processed", "error_message": False})
            except Exception as e:
                rec.write({"state": "error", "error_message": str(e)})

    def _create_credit_note(self):
        self.ensure_one()
        move_model = self.env["account.move"]
        order = self.order_id
        product = self.instance_id.discount_product_id or self.env["product.product"].search([("type", "=", "service")], limit=1)

        invoice_vals = {
            "move_type": "out_refund",
            "partner_id": order.partner_id.id,
            "currency_id": order.currency_id.id,
            "invoice_origin": f"Shopify Order {self.shopify_order_number or order.name}",
            "ref": f"Shopify Refund #{self.shopify_refund_id} - {self.reason or ''}",
            "invoice_date": fields.Date.context_today(self),
            "company_id": self.instance_id.company_id.id,
            "invoice_line_ids": [
                (0, 0, {
                    "name": f"Shopify Refund: {self.reason or 'Customer Refund'}",
                    "quantity": 1,
                    "price_unit": self.amount,
                    "product_id": product.id if product else False,
                })
            ],
        }
        credit_note = move_model.create(invoice_vals)
        self.credit_note_id = credit_note.id
        if self.instance_id.auto_validate_refunds:
            try:
                credit_note.action_post()
            except Exception:
                pass
        return credit_note


class ShopifyCategoryMapping(models.Model):
    _name = "shopify.category.mapping"
    _description = "Shopify Category / Collection Mapping"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_display_name")
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    category_id = fields.Many2one("product.category", string="Odoo Category", required=True, ondelete="cascade")
    shopify_collection_id = fields.Char(string="Shopify Collection ID", required=True, index=True)
    shopify_collection_title = fields.Char(string="Shopify Collection Title", required=True)
    shopify_collection_type = fields.Selection(
        selection=[
            ("custom", "Custom Collection"),
            ("smart", "Smart Collection"),
            ("product_type", "Product Type"),
        ],
        string="Collection Type",
        default="custom",
    )
    shopify_handle = fields.Char(string="Shopify URL Handle")

    _instance_shopify_collection_uniq = models.Constraint(
        "UNIQUE(instance_id, shopify_collection_id)",
        "The Shopify Collection ID must be unique per store!"
    )
    _instance_category_uniq = models.Constraint(
        "UNIQUE(instance_id, category_id)",
        "The Odoo Category is already mapped to this Shopify store!"
    )

    @api.depends("shopify_collection_title", "shopify_collection_id", "category_id", "category_id.name")
    def _compute_display_name(self):
        for rec in self:
            cat_name = rec.category_id.display_name or rec.category_id.name
            if cat_name:
                title = f"{rec.shopify_collection_title or 'Category'} ({cat_name})"
            else:
                title = rec.shopify_collection_title or f"Category Mapping #{rec.id}"
            rec.display_name = title
            rec.name = title
