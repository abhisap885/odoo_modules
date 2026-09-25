# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ShopifyFeed(models.Model):
    _name = "shopify.feed"
    _description = "Shopify Staging Data Feed"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Feed Reference", required=True, copy=False, default=lambda self: _("New Feed"))

    @api.depends("name", "feed_type", "external_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or f"Feed #{rec.external_id or rec.id} ({rec.feed_type or 'General'})"
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    feed_type = fields.Selection(
        selection=[
            ("order", "Sales Order"),
            ("product", "Product"),
            ("customer", "Customer"),
            ("category", "Category / Collection"),
        ],
        string="Feed Entity",
        required=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Pending"),
            ("done", "Processed"),
            ("error", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Processing Status",
        default="draft",
        required=True,
        index=True,
    )
    external_id = fields.Char(string="Shopify ID", index=True, required=True)
    raw_payload = fields.Text(string="Raw JSON Data", required=True)
    error_message = fields.Text(string="Error Details")

    # Link to created records
    order_id = fields.Many2one("sale.order", string="Generated Order", readonly=True)
    template_id = fields.Many2one("product.template", string="Generated Product", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Generated Customer", readonly=True)
    category_id = fields.Many2one("product.category", string="Generated Category", readonly=True)

    def action_process_feed(self):
        """Processes pending feeds into core Odoo database records."""
        for feed in self:
            if feed.state == "done":
                continue
            try:
                # Keep a failed feed from leaving the outer HTTP/cron
                # transaction in an aborted state.  The exception is handled
                # below, after this savepoint has rolled back its work.
                with self.env.cr.savepoint():
                    data = json.loads(feed.raw_payload)
                    if feed.feed_type == "order":
                        feed._process_order_feed(data)
                    elif feed.feed_type == "product":
                        feed._process_product_feed(data)
                    elif feed.feed_type == "customer":
                        feed._process_customer_feed(data)
                    elif feed.feed_type == "category":
                        feed._process_category_feed(data)
                    feed.write({"state": "done", "error_message": False})
            except Exception as e:
                _logger.exception("Failed to evaluate Shopify feed ID %s", feed.id)
                feed.write({
                    "state": "error",
                    "error_message": str(e),
                })

    def _resolve_country_and_state(self, country_code, province_code=None, province_name=None):
        """Resolves Odoo country and country state records from Shopify codes or names."""
        country = False
        if country_code:
            country = self.env["res.country"].search([
                "|", ("code", "=ilike", country_code.strip()), ("name", "=ilike", country_code.strip())
            ], limit=1)
        state = False
        if country and (province_code or province_name):
            domain = [("country_id", "=", country.id)]
            if province_code and province_name:
                domain.append("|")
                domain.append(("code", "=ilike", province_code.strip()))
                domain.append(("name", "=ilike", province_name.strip()))
            elif province_code:
                domain.append(("code", "=ilike", province_code.strip()))
            else:
                domain.append(("name", "=ilike", province_name.strip()))
            state = self.env["res.country.state"].search(domain, limit=1)
        return country, state

    def _sync_partner_address(self, parent_partner, address_data, addr_type="delivery"):
        """Creates or updates a child contact/address under the parent customer record."""
        partner_model = self.env["res.partner"]
        if not address_data:
            return False

        first_name = (address_data.get("first_name") or "").strip()
        last_name = (address_data.get("last_name") or "").strip()
        addr_name = f"{first_name} {last_name}".strip() or address_data.get("name") or parent_partner.name
        company = (address_data.get("company") or "").strip()
        street = address_data.get("address1") or address_data.get("street") or ""
        street2 = address_data.get("address2") or address_data.get("street2") or ""
        city = address_data.get("city") or ""
        zip_code = address_data.get("zip") or ""
        phone = address_data.get("phone") or parent_partner.phone or ""
        country_code = address_data.get("country_code") or address_data.get("countryCodeV2") or ""
        province_code = address_data.get("province_code") or address_data.get("provinceCode") or ""
        province_name = address_data.get("province") or ""

        country, state = self._resolve_country_and_state(country_code, province_code, province_name)

        # Check existing child contact by parent and address fields
        child_domain = [
            ("parent_id", "=", parent_partner.id),
            ("type", "=", addr_type),
        ]
        if street:
            child_domain.append(("street", "=ilike", street.strip()))
        if zip_code:
            child_domain.append(("zip", "=ilike", zip_code.strip()))

        child = partner_model.search(child_domain, limit=1)
        vals = {
            "name": addr_name,
            "parent_id": parent_partner.id,
            "type": addr_type,
            "street": street,
            "street2": street2,
            "city": city,
            "zip": zip_code,
            "state_id": state.id if state else False,
            "country_id": country.id if country else False,
            "phone": phone,
            "company_name": company or False,
            "company_id": parent_partner.company_id.id,
        }
        if child:
            child.write(vals)
        else:
            child = partner_model.create(vals)
        return child

    def _resolve_or_create_taxes(self, tax_lines, taxes_included=False, instance=None):
        """Resolves or creates Odoo account.tax records corresponding to Shopify tax_lines."""
        instance = instance or self.instance_id
        tax_model = self.env["account.tax"]
        tax_map_model = self.env["shopify.tax.mapping"]
        resolved_taxes = self.env["account.tax"]

        for tline in tax_lines or []:
            title = (tline.get("title") or "").strip()
            raw_rate = float(tline.get("rate") or 0.0)
            rate_pct = raw_rate * 100.0 if 0 < raw_rate < 1.0 else raw_rate

            # 1. Check existing mapping
            tmap = tax_map_model.search([
                ("instance_id", "=", instance.id),
                ("shopify_tax_title", "=", title),
            ], limit=1)
            if tmap and tmap.tax_id:
                resolved_taxes |= tmap.tax_id
                continue

            # 2. Search in account.tax
            existing_tax = tax_model.search([
                ("company_id", "=", instance.company_id.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", rate_pct),
                ("price_include", "=", bool(taxes_included)),
            ], limit=1)
            if not existing_tax:
                existing_tax = tax_model.search([
                    ("company_id", "=", instance.company_id.id),
                    ("type_tax_use", "=", "sale"),
                    ("amount", "=", rate_pct),
                ], limit=1)
            if not existing_tax and title:
                existing_tax = tax_model.search([
                    ("company_id", "=", instance.company_id.id),
                    ("type_tax_use", "=", "sale"),
                    ("name", "=ilike", title),
                ], limit=1)

            # 3. Create tax if not found
            if not existing_tax:
                tax_name = f"Shopify {title} ({round(rate_pct, 2)}%)" if title else f"Shopify Tax {round(rate_pct, 2)}%"
                existing_tax = tax_model.create({
                    "name": tax_name,
                    "type_tax_use": "sale",
                    "amount_type": "percent",
                    "amount": rate_pct,
                    "price_include": bool(taxes_included),
                    "company_id": instance.company_id.id,
                })

            if existing_tax:
                if not tmap:
                    tax_map_model.create({
                        "instance_id": instance.id,
                        "shopify_tax_title": title or existing_tax.name,
                        "tax_id": existing_tax.id,
                        "rate": rate_pct,
                    })
                resolved_taxes |= existing_tax

        return resolved_taxes

    def _process_customer_feed(self, data):
        self.ensure_one()
        mapping_model = self.env["shopify.partner.mapping"]
        partner_model = self.env["res.partner"]

        shopify_id = str(data.get("id"))
        email = (data.get("email") or "").strip()
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        name = f"{first_name} {last_name}".strip() or email or f"Shopify Customer #{shopify_id}"
        phone = (data.get("phone") or "").strip()

        # Parse primary / default address details
        default_addr = data.get("default_address") or (data.get("addresses", [{}])[0] if data.get("addresses") else {})
        parent_vals = {
            "name": name,
            "email": email,
            "phone": phone or default_addr.get("phone") or "",
            "customer_rank": 1,
            "type": "contact",
        }
        if default_addr:
            parent_vals["street"] = default_addr.get("address1") or ""
            parent_vals["street2"] = default_addr.get("address2") or ""
            parent_vals["city"] = default_addr.get("city") or ""
            parent_vals["zip"] = default_addr.get("zip") or ""
            if default_addr.get("company"):
                parent_vals["company_name"] = default_addr.get("company")
            c, s = self._resolve_country_and_state(
                default_addr.get("country_code"), default_addr.get("province_code"), default_addr.get("province")
            )
            if c:
                parent_vals["country_id"] = c.id
            if s:
                parent_vals["state_id"] = s.id

        # Check existing mapping
        mapping = mapping_model.search([("instance_id", "=", self.instance_id.id), ("shopify_customer_id", "=", shopify_id)], limit=1)
        if mapping:
            partner = mapping.partner_id
            partner.write(parent_vals)
        else:
            partner = partner_model.search([("email", "=", email), ("company_id", "in", [self.instance_id.company_id.id, False])], limit=1) if email else False
            if not partner:
                parent_vals["company_id"] = self.instance_id.company_id.id
                partner = partner_model.create(parent_vals)
            else:
                partner.write(parent_vals)

            mapping_model.create({
                "instance_id": self.instance_id.id,
                "partner_id": partner.id,
                "shopify_customer_id": shopify_id,
                "email": email,
                "phone": phone,
            })

        # Process Addresses Array (Create child contacts with type='invoice' or type='delivery')
        addresses = data.get("addresses") or []
        if addresses:
            for addr in addresses:
                addr_type = "invoice" if addr.get("default") else "delivery"
                self._sync_partner_address(partner, addr, addr_type=addr_type)
        elif default_addr:
            self._sync_partner_address(partner, default_addr, addr_type="invoice")

        # Process Customer Metafields
        if data.get("metafields"):
            self._process_metafields_for_record(partner, data.get("metafields"), "res.partner")

        self.partner_id = partner.id
        return partner

    def _sync_shopify_options(self, template, options):
        """Create Odoo attributes/values for Shopify product options.

        Shopify sends the available values at product level and the selected
        values on each variant (``option1`` through ``option3``).  Odoo needs
        the product template attribute lines before it can generate the same
        variant combinations.
        """
        attribute_model = self.env["product.attribute"]
        attribute_value_model = self.env["product.attribute.value"]
        attribute_line_model = self.env["product.template.attribute.line"]
        variant_options = []

        for option in options or []:
            name = (option.get("name") or "").strip()
            values = [str(value).strip() for value in option.get("values", []) if str(value).strip()]
            # Shopify's only variant is represented as "Title: Default Title";
            # it is not a real Odoo variant axis.
            if not name or (name.lower() == "title" and values == ["Default Title"]):
                continue

            attribute = attribute_model.search([("name", "=", name)], limit=1)
            if not attribute:
                attribute = attribute_model.create({"name": name, "create_variant": "always"})
            elif attribute.create_variant != "always":
                attribute.write({"create_variant": "always"})

            value_ids = []
            for value_name in values:
                value = attribute_value_model.search([
                    ("attribute_id", "=", attribute.id),
                    ("name", "=", value_name),
                ], limit=1)
                if not value:
                    value = attribute_value_model.create({
                        "attribute_id": attribute.id,
                        "name": value_name,
                    })
                value_ids.append(value.id)

            if not value_ids:
                continue
            line = attribute_line_model.search([
                ("product_tmpl_id", "=", template.id),
                ("attribute_id", "=", attribute.id),
            ], limit=1)
            if line:
                missing_value_ids = set(value_ids) - set(line.value_ids.ids)
                if missing_value_ids:
                    line.write({"value_ids": [(4, value_id) for value_id in missing_value_ids]})
            else:
                attribute_line_model.create({
                    "product_tmpl_id": template.id,
                    "attribute_id": attribute.id,
                    "value_ids": [(6, 0, value_ids)],
                })
            variant_options.append(attribute)

        if variant_options:
            template._create_variant_ids()
        return variant_options

    def _get_variant_for_shopify_options(self, template, variant, attributes):
        """Return the Odoo product matching a Shopify variant combination."""
        if not attributes:
            return template.product_variant_id

        ptav_model = self.env["product.template.attribute.value"]
        selected_ptav_ids = []
        for index, attribute in enumerate(attributes, start=1):
            value_name = variant.get("option%s" % index)
            if value_name in (None, ""):
                return self.env["product.product"]
            attribute_value = self.env["product.attribute.value"].search([
                ("attribute_id", "=", attribute.id),
                ("name", "=", str(value_name)),
            ], limit=1)
            ptav = ptav_model.search([
                ("product_tmpl_id", "=", template.id),
                ("product_attribute_value_id", "=", attribute_value.id),
            ], limit=1)
            if not ptav:
                return self.env["product.product"]
            selected_ptav_ids.append(ptav.id)

        selected_ptav_ids = set(selected_ptav_ids)
        return template.product_variant_ids.filtered(
            lambda product: set(product.product_template_attribute_value_ids.ids) == selected_ptav_ids
        )[:1]

    def _process_product_feed(self, data):
        self.ensure_one()
        template_map_model = self.env["shopify.template.mapping"]
        product_map_model = self.env["shopify.product.mapping"]
        tmpl_model = self.env["product.template"]

        shopify_product_id = str(data.get("id"))
        title = data.get("title") or _("Untitled Shopify Product")
        handle = data.get("handle") or ""
        body_html = data.get("body_html") or ""
        variants = data.get("variants", [])

        # Check existing template mapping
        tmpl_mapping = template_map_model.search([
            ("instance_id", "=", self.instance_id.id),
            ("shopify_product_id", "=", shopify_product_id)
        ], limit=1)
        is_first_product_import = not bool(tmpl_mapping)

        if tmpl_mapping:
            template = tmpl_mapping.template_id
            template.write({
                "name": title,
                "description_sale": body_html,
                # Shopify products handled by this connector have an
                # inventory-item mapping, so Odoo must track their on-hand
                # quantity for inventory import/export to work.
                "is_storable": True,
            })
        else:
            template = tmpl_model.create({
                "name": title,
                "description_sale": body_html,
                "is_storable": True,
                "company_id": self.instance_id.company_id.id,
            })
            tmpl_mapping = template_map_model.create({
                "instance_id": self.instance_id.id,
                "template_id": template.id,
                "shopify_product_id": shopify_product_id,
                "shopify_handle": handle,
            })

        attributes = self._sync_shopify_options(template, data.get("options", []))

        # Process Variants
        imported_variant_maps = self.env["shopify.product.mapping"]
        for var in variants:
            var_id = str(var.get("id"))
            sku = var.get("sku") or ""
            barcode = var.get("barcode") or False
            price = float(var.get("price") or 0.0)
            inv_item_id = str(var.get("inventory_item_id") or "")

            var_mapping = product_map_model.search([
                ("instance_id", "=", self.instance_id.id),
                ("shopify_variant_id", "=", var_id)
            ], limit=1)

            if var_mapping:
                # Reconcile mappings created by older connector versions,
                # which linked every Shopify variant to the template's first
                # Odoo product.
                product = self._get_variant_for_shopify_options(template, var, attributes) or var_mapping.product_id
                product.write({
                    "default_code": sku or product.default_code,
                    "barcode": barcode or product.barcode,
                    "list_price": price,
                })
                var_mapping.write({
                    "template_mapping_id": tmpl_mapping.id,
                    "product_id": product.id,
                    "shopify_sku": sku,
                    "shopify_inventory_item_id": inv_item_id,
                })
                imported_variant_maps |= var_mapping
                self.instance_id.set_product_pricelist_price(product, price)
            else:
                # Select the Odoo variant matching Shopify's option values,
                # rather than reusing the template's first variant.
                product = self._get_variant_for_shopify_options(template, var, attributes)
                if not product:
                    raise UserError(_("Could not create an Odoo variant for Shopify variant %s.") % var_id)
                product.write({
                    "default_code": sku or product.default_code,
                    "barcode": barcode or product.barcode,
                    "list_price": price,
                })

                # A product can already have a mapping when Shopify replaces
                # a variant ID or a prior import was only partly completed.
                # Reuse that mapping instead of violating the unique
                # (instance_id, product_id) constraint.
                product_mapping_vals = {
                    "instance_id": self.instance_id.id,
                    "template_mapping_id": tmpl_mapping.id,
                    "product_id": product.id,
                    "shopify_variant_id": var_id,
                    "shopify_sku": sku,
                    "shopify_inventory_item_id": inv_item_id,
                }
                existing_product_mapping = product_map_model.search([
                    ("instance_id", "=", self.instance_id.id),
                    ("product_id", "=", product.id),
                ], limit=1)
                if existing_product_mapping:
                    existing_product_mapping.write(product_mapping_vals)
                    imported_variant_maps |= existing_product_mapping
                else:
                    imported_variant_maps |= product_map_model.create(product_mapping_vals)
                self.instance_id.set_product_pricelist_price(product, price)

            # Process Variant Metafields
            if var.get("metafields"):
                self._process_metafields_for_record(product, var.get("metafields"), "product.product")

        if not variants and data.get("price"):
            self.instance_id.set_product_pricelist_price(template, float(data.get("price") or 0.0))

        # Process Template Metafields
        if data.get("metafields"):
            self._process_metafields_for_record(template, data.get("metafields"), "product.template")

        # Resolve and import all categories/collections for this product
        resolved_categories = self.env["product.category"]

        # 1. Parse collections list if present (e.g. [{"id": 123, "title": "Summer Collection"}])
        raw_collections = data.get("collections", [])
        if isinstance(raw_collections, list):
            for col in raw_collections:
                if isinstance(col, dict):
                    col_id = col.get("id")
                    col_title = col.get("title") or col.get("name")
                    col_type = col.get("collection_type", "custom")
                    col_handle = col.get("handle")
                    cat = self.instance_id._get_or_create_category(col_id, col_title, col_type, col_handle)
                    if cat:
                        resolved_categories |= cat
                elif isinstance(col, (str, int)):
                    cat = self.instance_id._get_or_create_category(str(col))
                    if cat:
                        resolved_categories |= cat

        # 2. Parse collection_ids or extra_categ_ids (comma-separated or list of IDs)
        extra_ids = data.get("collection_ids") or data.get("extra_categ_ids") or []
        if isinstance(extra_ids, str):
            extra_ids = [c.strip() for c in extra_ids.split(",") if c.strip()]
        for cid in extra_ids:
            cat = self.instance_id._get_or_create_category(str(cid))
            if cat:
                resolved_categories |= cat

        # 3. Parse product_type (e.g. "Snowboard", "Clothing")
        product_type = data.get("product_type")
        if product_type and isinstance(product_type, str) and product_type.strip():
            type_title = product_type.strip()
            cat = self.instance_id._get_or_create_category(
                f"type_{type_title.lower()}", categ_title=type_title, categ_type="product_type"
            )
            if cat:
                resolved_categories |= cat

        # Assign categories to template
        template_category_vals = {}
        if resolved_categories:
            template_category_vals["shopify_category_ids"] = [(6, 0, resolved_categories.ids)]
            template_category_vals["categ_id"] = resolved_categories[0].id
        if template_category_vals:
            template.write(template_category_vals)

        if is_first_product_import and imported_variant_maps and self.instance_id.state == "confirmed":
            self._sync_inventory_from_shopify(
                self.instance_id,
                inventory_item_ids=imported_variant_maps.mapped("shopify_inventory_item_id"),
            )

        self.template_id = template.id
        return template

    def _process_category_feed(self, data):
        """Processes category/collection feed into product.category and shopify.category.mapping."""
        self.ensure_one()
        cat_map_model = self.env["shopify.category.mapping"]
        cat_model = self.env["product.category"]

        store_id = str(data.get("id"))
        title = (data.get("title") or data.get("name") or _("Untitled Collection")).strip()
        handle = data.get("handle") or ""
        col_type = data.get("collection_type") or "custom"

        mapping = cat_map_model.search([
            ("instance_id", "=", self.instance_id.id),
            ("shopify_collection_id", "=", store_id),
        ], limit=1)

        if mapping:
            category = mapping.category_id
            category.write({"name": title})
            mapping.write({
                "shopify_collection_title": title,
                "shopify_handle": handle,
                "shopify_collection_type": col_type,
            })
        else:
            category = cat_model.search([("name", "=ilike", title)], limit=1)
            if not category:
                category = cat_model.create({"name": title})

            cat_map_model.create({
                "instance_id": self.instance_id.id,
                "category_id": category.id,
                "shopify_collection_id": store_id,
                "shopify_collection_title": title,
                "shopify_handle": handle,
                "shopify_collection_type": col_type,
            })

        self.category_id = category.id
        return category

    @api.model
    def _get_inventory_target_locations(self, instance):
        loc_maps = instance.location_mapping_ids.filtered(lambda l: l.sync_stock and l.active and l.location_id)
        targets = []
        for lmap in loc_maps:
            targets.append((lmap.shopify_location_id, lmap.location_id, lmap.shopify_location_name))
        if not targets and instance.shopify_location_id:
            stock_loc = instance.location_id or (instance.warehouse_id.lot_stock_id if instance.warehouse_id else False)
            if not stock_loc:
                stock_loc = self.env["stock.location"].search([
                    ("usage", "=", "internal"),
                    ("company_id", "in", [instance.company_id.id, False]),
                ], limit=1)
            if stock_loc:
                targets.append((instance.shopify_location_id, stock_loc, _("Primary Location")))
        return targets

    @api.model
    def _chunked(self, values, size=50):
        clean_values = [value for value in values if value]
        for index in range(0, len(clean_values), size):
            yield clean_values[index:index + size]

    @api.model
    def _apply_inventory_levels(self, instance, levels, stock_loc):
        quant_model = self.env["stock.quant"]
        product_map_model = self.env["shopify.product.mapping"]
        synced_count = 0
        for lvl in levels:
            inv_item_id = str(lvl.get("inventory_item_id") or "")
            avail_qty = float(lvl.get("available") or 0.0)
            vmap = product_map_model.search([
                ("instance_id", "=", instance.id),
                ("shopify_inventory_item_id", "=", inv_item_id),
            ], limit=1)
            if not vmap or not vmap.product_id:
                continue
            quant = quant_model.search([
                ("product_id", "=", vmap.product_id.id),
                ("location_id", "=", stock_loc.id),
                ("lot_id", "=", False),
                ("package_id", "=", False),
                ("owner_id", "=", False),
            ], limit=1)
            if not quant:
                quant = quant_model.create({
                    "product_id": vmap.product_id.id,
                    "location_id": stock_loc.id,
                })
            quant.inventory_quantity = avail_qty
            quant.with_context(skip_shopify_realtime_inventory=True).action_apply_inventory()
            synced_count += 1
        return synced_count

    @api.model
    def _sync_inventory_from_shopify(self, instance, client=None, inventory_item_ids=None, limit=100):
        targets = self._get_inventory_target_locations(instance)
        if not targets:
            return 0
        client = client or instance.get_api_client()
        inventory_item_ids = [str(item_id) for item_id in (inventory_item_ids or []) if item_id]
        synced_count = 0
        for shopify_loc_id, stock_loc, loc_name in targets:
            try:
                if inventory_item_ids:
                    for item_chunk in self._chunked(inventory_item_ids, 50):
                        levels = client.fetch_inventory_levels(
                            location_ids=shopify_loc_id,
                            inventory_item_ids=item_chunk,
                            limit=limit,
                        )
                        synced_count += self._apply_inventory_levels(instance, levels, stock_loc)
                else:
                    levels = client.fetch_inventory_levels(location_ids=shopify_loc_id, limit=limit)
                    synced_count += self._apply_inventory_levels(instance, levels, stock_loc)
            except Exception as e:
                _logger.warning("Failed to import inventory levels for location %s: %s", loc_name, str(e))
        if synced_count:
            instance.last_inventory_sync = fields.Datetime.now()
        return synced_count

    def _process_order_feed(self, data):
        self.ensure_one()
        order_map_model = self.env["shopify.order.mapping"]
        order_model = self.env["sale.order"]
        product_map_model = self.env["shopify.product.mapping"]

        shopify_order_id = str(data.get("id"))
        order_number = str(data.get("order_number") or data.get("name") or shopify_order_id)
        financial_status = data.get("financial_status") or "pending"
        fulfillment_status = data.get("fulfillment_status") or "unfulfilled"

        raw_created_at = data.get("created_at")
        date_order = fields.Datetime.now()
        if raw_created_at:
            try:
                from datetime import datetime
                cleaned_dt = raw_created_at.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(cleaned_dt)
                date_order = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                date_order = fields.Datetime.now()

        # Check existing order mapping
        existing_map = order_map_model.search([
            ("instance_id", "=", self.instance_id.id),
            ("shopify_order_id", "=", shopify_order_id)
        ], limit=1)
        if existing_map:
            self.order_id = existing_map.order_id.id
            existing_map.write({
                "financial_status": financial_status,
                "fulfillment_status": fulfillment_status,
            })
            if data.get("refunds"):
                self._process_order_refunds(existing_map.order_id, shopify_order_id, order_number, data.get("refunds"))
            return existing_map.order_id

        # Resolve Warehouse based on Location Mapping
        warehouse = self.instance_id.warehouse_id
        shopify_loc_id = str(data.get("location_id") or "")
        if not shopify_loc_id and data.get("fulfillments"):
            for f in data.get("fulfillments", []):
                if f.get("location_id"):
                    shopify_loc_id = str(f.get("location_id"))
                    break
        if shopify_loc_id:
            loc_map = self.env["shopify.location.mapping"].search([
                ("instance_id", "=", self.instance_id.id),
                ("shopify_location_id", "=", shopify_loc_id),
            ], limit=1)
            if loc_map and loc_map.warehouse_id:
                warehouse = loc_map.warehouse_id

        # Resolve or create Customer & Addresses
        customer_data = data.get("customer") or {}
        if customer_data:
            partner = self._process_customer_feed(customer_data)
        else:
            billing_addr = data.get("billing_address") or {}
            email = (data.get("email") or "").strip()
            name = billing_addr.get("name") or email or f"Shopify Customer #{shopify_order_id}"
            partner = self.env["res.partner"].search([
                ("email", "=", email),
                ("company_id", "in", [self.instance_id.company_id.id, False]),
            ], limit=1) if email else False
            if not partner:
                partner = self.env["res.partner"].create({
                    "name": name,
                    "email": email,
                    "customer_rank": 1,
                    "company_id": self.instance_id.company_id.id,
                })

        invoice_partner = partner
        shipping_partner = partner

        billing_data = data.get("billing_address")
        if billing_data:
            invoice_partner = self._sync_partner_address(partner, billing_data, addr_type="invoice") or partner

        shipping_data = data.get("shipping_address")
        if shipping_data:
            shipping_partner = self._sync_partner_address(partner, shipping_data, addr_type="delivery") or partner
        elif billing_data:
            shipping_partner = invoice_partner

        # Order Lines
        order_lines_vals = []
        taxes_included = bool(data.get("taxes_included", False))

        for line in data.get("line_items", []):
            variant_id = str(line.get("variant_id") or "")
            qty = float(line.get("quantity") or 1.0)
            price = float(line.get("price") or 0.0)
            title = line.get("name") or _("Shopify Item")

            var_mapping = product_map_model.search([
                ("instance_id", "=", self.instance_id.id),
                ("shopify_variant_id", "=", variant_id)
            ], limit=1) if variant_id else False

            if var_mapping:
                product = var_mapping.product_id
            else:
                sku = line.get("sku")
                product = self.env["product.product"].search([("default_code", "=", sku)], limit=1) if sku else False
                if not product:
                    product = self.env["product.product"].with_company(self.instance_id.company_id).create({
                        "name": title,
                        "default_code": sku or f"SHOPIFY-{variant_id or line.get('id')}",
                        "list_price": price,
                        "type": "consu",
                        "company_id": self.instance_id.company_id.id,
                    })
                    self.instance_id.set_product_pricelist_price(product, price)

            # Calculate line discount from allocations
            line_disc_amt = 0.0
            for da in line.get("discount_allocations", []):
                amt = da.get("amount") or da.get("allocated_amount") or da.get("allocatedAmountSet", {}).get("shopMoney", {}).get("amount", 0.0)
                line_disc_amt += float(amt or 0.0)

            discount_pct = 0.0
            total_gross = price * qty
            if line_disc_amt > 0 and total_gross > 0:
                discount_pct = min(100.0, (line_disc_amt / total_gross) * 100.0)

            # Resolve line taxes
            tax_lines = line.get("tax_lines") or []
            resolved_taxes = self._resolve_or_create_taxes(tax_lines, taxes_included=taxes_included, instance=self.instance_id)

            order_lines_vals.append((0, 0, {
                "product_id": product.id,
                "name": title,
                "product_uom_qty": qty,
                "price_unit": price,
                "discount": round(discount_pct, 2) if discount_pct > 0 else 0.0,
                "tax_ids": [(6, 0, resolved_taxes.ids)],
            }))

        # Shipping Lines
        for sline in data.get("shipping_lines", []):
            stitle = sline.get("title") or _("Shipping & Handling")
            sprice = float(sline.get("price") or 0.0)
            staxes = self._resolve_or_create_taxes(
                sline.get("tax_lines") or [], taxes_included=taxes_included, instance=self.instance_id
            )
            deliv_product = self.instance_id._get_or_create_delivery_product()
            order_lines_vals.append((0, 0, {
                "product_id": deliv_product.id,
                "name": f"Shipping: {stitle}",
                "product_uom_qty": 1.0,
                "price_unit": sprice,
                "tax_ids": [(6, 0, staxes.ids)],
            }))

        # Order-Level Manual Discounts (unallocated discount applications)
        for dapp in data.get("discount_applications", []):
            target_type = dapp.get("target_type")
            alloc_method = dapp.get("allocation_method")
            if alloc_method == "across" or target_type == "shipping":
                continue
            disc_val = float(dapp.get("value") or 0.0)
            disc_title = dapp.get("title") or dapp.get("code") or _("Shopify Order Discount")
            if disc_val > 0:
                disc_product = self.instance_id._get_or_create_discount_product()
                order_lines_vals.append((0, 0, {
                    "product_id": disc_product.id,
                    "name": f"Discount: {disc_title}",
                    "product_uom_qty": 1.0,
                    "price_unit": -abs(disc_val),
                }))

        # Resolve Pricelist matching order currency & instance company
        order_currency = data.get("currency") or data.get("presentment_currency")
        pricelist = self.instance_id._get_or_create_pricelist_for_currency(order_currency)

        # Create Order
        order_vals = {
            "partner_id": partner.id,
            "partner_invoice_id": invoice_partner.id,
            "partner_shipping_id": shipping_partner.id,
            "company_id": self.instance_id.company_id.id,
            "warehouse_id": warehouse.id if warehouse else self.instance_id.warehouse_id.id,
            "team_id": self.instance_id.team_id.id if self.instance_id.team_id else False,
            "user_id": self.instance_id.user_id.id if self.instance_id.user_id else False,
            "pricelist_id": pricelist.id,
            "date_order": date_order,
            "origin": f"Shopify #{order_number}",
            "order_line": order_lines_vals,
        }
        if self.instance_id.payment_term_id:
            order_vals["payment_term_id"] = self.instance_id.payment_term_id.id

        sale_order = order_model.create(order_vals)

        # Create Order Mapping
        order_map_model.create({
            "instance_id": self.instance_id.id,
            "order_id": sale_order.id,
            "shopify_order_id": shopify_order_id,
            "shopify_order_number": order_number,
            "financial_status": financial_status,
            "fulfillment_status": fulfillment_status,
        })

        # Automated Workflows: Order Confirmation, Invoicing, Payment, Delivery
        payment_gateways = data.get("payment_gateway_names") or []
        primary_gateway = payment_gateways[0] if payment_gateways else ""

        should_confirm = (
            self.instance_id.auto_validate_orders
            or financial_status == "paid"
            or fulfillment_status == "fulfilled"
        )
        if should_confirm and sale_order.state == "draft":
            sale_order.action_confirm()

        # Invoicing and Payment
        should_invoice = (financial_status == "paid" or self.instance_id.auto_create_invoices)
        if should_invoice and sale_order.state in ("sale", "done"):
            if not sale_order.invoice_ids:
                try:
                    invoices = sale_order.with_company(self.instance_id.company_id)._create_invoices()
                    for inv in invoices:
                        if sale_order.date_order:
                            inv.invoice_date = sale_order.date_order.date()
                        inv.with_company(self.instance_id.company_id).action_post()

                        if financial_status == "paid" and self.instance_id.auto_paid_invoices:
                            journal = self.instance_id._get_payment_journal(primary_gateway)
                            if journal and inv.amount_residual > 0:
                                reg_wiz = self.env["account.payment.register"].with_company(self.instance_id.company_id).with_context(
                                    active_model="account.move",
                                    active_ids=[inv.id],
                                ).create({
                                    "journal_id": journal.id,
                                    "payment_date": inv.invoice_date,
                                    "amount": inv.amount_residual,
                                })
                                reg_wiz.action_create_payments()
                except Exception as e:
                    _logger.warning("Could not auto-create/post invoice for order %s: %s", sale_order.name, str(e))

        # Delivery / Fulfillment Validation
        should_deliver = (fulfillment_status == "fulfilled" or self.instance_id.auto_deliver_orders)
        if should_deliver and sale_order.picking_ids:
            for picking in sale_order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
                try:
                    if picking.state == "draft":
                        picking.action_confirm()
                    if picking.state != "assigned":
                        picking.action_assign()
                    for move in picking.move_ids:
                        if move.move_line_ids:
                            for ml in move.move_line_ids:
                                ml.quantity = ml.quantity_product_uom
                        else:
                            move.quantity = move.product_uom_qty
                    picking.with_company(self.instance_id.company_id).with_context(
                        skip_backorder=True,
                        skip_sms=True,
                        skip_shopify_realtime_inventory=True,
                    ).button_validate()
                    picking.shopify_fulfillment_synced = True
                except Exception as e:
                    _logger.warning("Could not auto-deliver order %s picking %s: %s", sale_order.name, picking.name, str(e))

        # Process Order Metafields
        if data.get("metafields"):
            self._process_metafields_for_record(sale_order, data.get("metafields"), "sale.order")

        # Process Order Refunds
        if data.get("refunds"):
            self._process_order_refunds(sale_order, shopify_order_id, order_number, data.get("refunds"))

        self.order_id = sale_order.id
        return sale_order

    def _process_order_refunds(self, order, shopify_order_id, order_number, refunds_data):
        """Processes refunds associated with an order, creating credit notes and mapping records."""
        refund_map_model = self.env["shopify.refund.mapping"]
        for refund in refunds_data:
            refund_id = str(refund.get("id"))
            existing = refund_map_model.search([
                ("instance_id", "=", self.instance_id.id),
                ("shopify_refund_id", "=", refund_id),
            ], limit=1)
            if existing:
                continue

            amount = 0.0
            if refund.get("transactions"):
                amount = sum(float(tx.get("amount") or 0.0) for tx in refund.get("transactions") if tx.get("status") in ("success", "pending"))
            elif refund.get("totalRefundedSet"):
                amount = float(refund.get("totalRefundedSet", {}).get("shopMoney", {}).get("amount") or 0.0)

            reason = refund.get("note") or "Shopify Order Refund"
            raw_date = refund.get("created_at")
            refund_date = fields.Datetime.now()
            if raw_date:
                try:
                    cleaned_date = raw_date.replace("Z", "+00:00")
                    from datetime import datetime
                    parsed_dt = datetime.fromisoformat(cleaned_date)
                    refund_date = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    refund_date = fields.Datetime.now()

            refund_rec = refund_map_model.create({
                "instance_id": self.instance_id.id,
                "shopify_refund_id": refund_id,
                "shopify_order_id": shopify_order_id,
                "shopify_order_number": order_number,
                "order_id": order.id,
                "amount": amount,
                "reason": reason,
                "date_refund": refund_date,
                "state": "draft",
            })
            if self.instance_id.auto_process_refunds:
                refund_rec.action_process_refund()

    def _process_metafields_for_record(self, record, metafields_data, model_name):
        """Import Shopify metafields into mapped Odoo fields or product sheet values."""
        if not metafields_data or not record:
            return
        mappings = self.env["shopify.metafield.mapping"].search([
            ("instance_id", "=", self.instance_id.id),
            ("model_name", "=", model_name),
            ("sync_direction", "in", ("both", "import")),
            ("active", "=", True),
        ])
        if not mappings:
            return

        meta_dict = {}
        for item in metafields_data:
            ns = item.get("namespace", "custom")
            k = item.get("key")
            val = item.get("value")
            if k is not None:
                meta_dict[(ns, k)] = val

        write_vals = {}
        for mapping in mappings:
            lookup_key = (mapping.namespace, mapping.key)
            if lookup_key not in meta_dict:
                continue

            raw_val = meta_dict[lookup_key]
            if mapping.store_type == "field" and mapping.field_id:
                parsed_val = self._convert_metafield_value(raw_val, mapping.metafield_type, mapping.field_id.ttype)
                if parsed_val is not None:
                    write_vals[mapping.field_id.name] = parsed_val
            elif mapping.store_type == "custom" and model_name in ("product.template", "product.product"):
                self._upsert_product_metafield_value(record, mapping, raw_val, model_name)

        if write_vals:
            try:
                record.write(write_vals)
            except Exception as e:
                _logger.warning("Failed to write metafields to %s ID %s: %s", model_name, record.id, str(e))

    def _upsert_product_metafield_value(self, record, mapping, raw_val, model_name):
        value_model = self.env["shopify.metafield.value"]
        domain = [
            ("instance_id", "=", self.instance_id.id),
            ("mapping_id", "=", mapping.id),
        ]
        vals = {
            "instance_id": self.instance_id.id,
            "mapping_id": mapping.id,
            "value": "" if raw_val is None else str(raw_val),
        }
        if model_name == "product.template":
            domain.append(("product_tmpl_id", "=", record.id))
            vals["product_tmpl_id"] = record.id
        else:
            domain.append(("product_id", "=", record.id))
            vals["product_id"] = record.id

        existing = value_model.search(domain, limit=1)
        if existing:
            existing.write({"value": vals["value"]})
        else:
            value_model.create(vals)

    def _convert_metafield_value(self, raw_val, metafield_type, odoo_ttype):
        if raw_val is None:
            return None
        try:
            if odoo_ttype == "boolean" or metafield_type == "boolean":
                return str(raw_val).lower() in ("true", "1", "t", "yes")
            elif odoo_ttype == "integer" or metafield_type == "number_integer":
                return int(float(raw_val))
            elif odoo_ttype == "float" or metafield_type == "number_decimal":
                return float(raw_val)
            elif odoo_ttype in ("char", "text", "html"):
                return str(raw_val)
            return raw_val
        except Exception as e:
            _logger.warning("Could not convert metafield value '%s': %s", raw_val, str(e))
            return None
