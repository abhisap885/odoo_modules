# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ShopifySyncWizard(models.TransientModel):
    _name = "shopify.sync.wizard"
    _description = "Shopify Synchronization Operations Wizard"

    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True)
    operation_type = fields.Selection(
        selection=[
            ("import", "Import from Shopify"),
            ("export", "Export to Shopify"),
        ],
        string="Action Type",
        default="import",
        required=True,
    )
    entity_type = fields.Selection(
        selection=[
            ("order", "Sales Orders"),
            ("product", "Products & Variants"),
            ("category", "Categories / Collections"),
            ("customer", "Customers"),
            ("stock", "Inventory Quantities"),
            ("metafield", "Metafield Definitions"),
            ("refund", "Order Refunds"),
        ],
        string="Target Entity",
        default="order",
        required=True,
    )
    record_limit = fields.Integer(string="Max Records to Fetch", default=50, help="Number of records to fetch per request (max 250).")
    date_from = fields.Datetime(string="Updated Since", help="Only fetch records updated after this timestamp.")
    auto_process_feed = fields.Boolean(string="Immediately Process Feeds", default=True, help="Automatically transform staging feeds into live Odoo records.")

    def _get_export_option_lines(self, template):
        return template.attribute_line_ids.filtered(
            lambda line: line.attribute_id.create_variant != "no_variant"
        )[:3]

    def _get_export_variant_for_shopify_options(self, template, shopify_variant, option_lines):
        if not option_lines:
            return template.product_variant_id

        expected_values = {}
        for index, line in enumerate(option_lines, start=1):
            value = shopify_variant.get("option%s" % index)
            if value not in (None, ""):
                expected_values[line.attribute_id.id] = str(value)

        if not expected_values:
            return self.env["product.product"]

        for variant in template.product_variant_ids:
            selected_values = {
                ptav.attribute_id.id: ptav.product_attribute_value_id.name
                for ptav in variant.product_template_attribute_value_ids
            }
            if all(selected_values.get(attribute_id) == value for attribute_id, value in expected_values.items()):
                return variant
        return self.env["product.product"]

    def _prepare_shopify_product_payload(self, template, metafields=None, template_mapping=None):
        """Build REST payload with Shopify options and variant combinations."""
        attribute_lines = self._get_export_option_lines(template)
        pricelist = self.instance_id.pricelist_id
        variants = []
        for variant in template.product_variant_ids:
            selected_values = {
                ptav.attribute_id.id: ptav.product_attribute_value_id.name
                for ptav in variant.product_template_attribute_value_ids
            }
            price_val = variant.list_price
            if pricelist:
                try:
                    price_val = pricelist._get_product_price(variant, 1.0) or variant.list_price
                except Exception:
                    price_val = variant.list_price
            variant_payload = {
                "sku": variant.default_code or f"ODOO-{variant.id}",
                "price": str(price_val),
                "barcode": variant.barcode or "",
            }
            if variant.is_storable:
                variant_payload["inventory_management"] = "shopify"
            for index, line in enumerate(attribute_lines[:3], start=1):
                value = selected_values.get(line.attribute_id.id)
                if value:
                    variant_payload["option%s" % index] = value
            if template_mapping:
                variant_mapping = template_mapping.variant_mapping_ids.filtered(lambda m: m.product_id == variant)[:1]
                if variant_mapping and variant_mapping.shopify_variant_id:
                    variant_id = str(variant_mapping.shopify_variant_id)
                    variant_payload["id"] = int(variant_id) if variant_id.isdigit() else variant_id
            variants.append(variant_payload)

        fallback_price = template.list_price
        if pricelist:
            try:
                first_var = template.product_variant_ids[:1]
                if first_var:
                    fallback_price = pricelist._get_product_price(first_var, 1.0) or template.list_price
            except Exception:
                fallback_price = template.list_price

        fallback_variant = {
            "price": str(fallback_price),
            "sku": template.default_code or f"ODOO-TMPL-{template.id}",
        }
        if template.is_storable:
            fallback_variant["inventory_management"] = "shopify"
        payload = {
            "title": template.name,
            "body_html": template.description_sale or "",
            "variants": variants or [fallback_variant],
        }
        if attribute_lines:
            payload["options"] = [
                {
                    "name": line.attribute_id.name,
                    "values": line.value_ids.mapped("name"),
                }
                for line in attribute_lines[:3]
            ]
        if metafields:
            payload["metafields"] = metafields
        return payload

    def _attach_product_metafields(self, client, product_data):
        """Fetch product and variant metafields that Shopify does not include in products.json."""
        product_id = product_data.get("id")
        if product_id:
            try:
                product_data["metafields"] = client.fetch_metafields("products", product_id)
            except Exception as e:
                _logger.warning("Failed to fetch metafields for Shopify product %s: %s", product_id, str(e))

        for variant in product_data.get("variants", []) or []:
            variant_id = variant.get("id")
            if not variant_id:
                continue
            try:
                variant["metafields"] = client.fetch_metafields("variants", variant_id)
            except Exception as e:
                _logger.warning("Failed to fetch metafields for Shopify variant %s: %s", variant_id, str(e))
        return product_data

    def _attach_product_collections(self, client, product_data):
        """Fetch collections for a product and attach to product payload."""
        product_id = product_data.get("id")
        if not product_id:
            return product_data
        try:
            collects = client.fetch_collects(product_id=product_id)
            if collects:
                product_data["collection_ids"] = [str(c.get("collection_id")) for c in collects if c.get("collection_id")]
        except Exception as e:
            _logger.warning("Failed to fetch collections for Shopify product %s: %s", product_id, str(e))
        return product_data

    def _format_metafield_export_value(self, value, metafield_type):
        if value in (False, None, ""):
            return ""
        if metafield_type == "boolean":
            return "true" if bool(value) else "false"
        if metafield_type in ("json",):
            return value if isinstance(value, str) else json.dumps(value)
        return str(value)

    def _collect_record_metafields(self, record, model_name, instance):
        mappings = self.env["shopify.metafield.mapping"].search([
            ("instance_id", "=", instance.id),
            ("model_name", "=", model_name),
            ("sync_direction", "in", ("both", "export")),
            ("active", "=", True),
        ])
        metafields = []
        for mapping in mappings:
            if mapping.namespace == "shopify":
                continue
            raw_value = False
            if mapping.store_type == "field" and mapping.field_id:
                raw_value = record[mapping.field_id.name]
            elif mapping.store_type == "custom" and model_name in ("product.template", "product.product"):
                value_domain = [
                    ("instance_id", "=", instance.id),
                    ("mapping_id", "=", mapping.id),
                ]
                if model_name == "product.template":
                    value_domain.append(("product_tmpl_id", "=", record.id))
                else:
                    value_domain.append(("product_id", "=", record.id))
                line = self.env["shopify.metafield.value"].search(value_domain, limit=1)
                raw_value = line.value if line else False

            value = self._format_metafield_export_value(raw_value, mapping.metafield_type)
            if value:
                metafields.append({
                    "namespace": mapping.namespace or "custom",
                    "key": mapping.key,
                    "value": value,
                    "type": mapping.metafield_type,
                })
        return metafields

    def _push_metafields(self, client, resource_type, resource_id, metafields):
        synced_count = 0
        for metafield in metafields:
            try:
                client.set_metafield(resource_type, resource_id, metafield)
                synced_count += 1
            except Exception as e:
                _logger.warning(
                    "Failed to sync Shopify metafield %s.%s on %s %s: %s",
                    metafield.get("namespace"), metafield.get("key"), resource_type, resource_id, str(e)
                )
        return synced_count

    def _sync_initial_inventory_to_shopify(self, client, instance, variant_maps):
        """Push stock once after creating products on Shopify."""
        synced_count = 0
        variant_maps = variant_maps.filtered(lambda m: m.shopify_inventory_item_id and m.product_id and m.product_id.is_storable)
        if not variant_maps:
            return synced_count

        loc_maps = instance.location_mapping_ids.filtered(lambda l: l.sync_stock and l.active and l.location_id)
        if loc_maps:
            for lmap in loc_maps:
                for vmap in variant_maps:
                    qty = instance.get_stock_quantity(vmap.product_id, lmap.location_id)
                    try:
                        client.update_inventory_level(
                            inventory_item_id=vmap.shopify_inventory_item_id,
                            location_id=lmap.shopify_location_id,
                            available_qty=qty,
                        )
                        synced_count += 1
                    except Exception as e:
                        _logger.warning(
                            "Failed to sync initial inventory for variant %s at location %s: %s",
                            vmap.product_id.display_name, lmap.shopify_location_name, str(e)
                        )
            return synced_count

        if not instance.shopify_location_id:
            _logger.warning(
                "Skipping initial inventory export for Shopify store %s because no Shopify location is configured.",
                instance.display_name,
            )
            return synced_count

        for vmap in variant_maps:
            qty = int(vmap.product_id.qty_available)
            try:
                client.update_inventory_level(
                    inventory_item_id=vmap.shopify_inventory_item_id,
                    location_id=instance.shopify_location_id,
                    available_qty=qty,
                )
                synced_count += 1
            except Exception as e:
                _logger.warning("Failed to sync initial inventory for variant %s: %s", vmap.product_id.display_name, str(e))
        return synced_count

    def action_execute_sync(self):
        """Executes the chosen synchronization procedure."""
        self.ensure_one()
        instance = self.instance_id
        if instance.state != "confirmed":
            raise UserError(_("The Shopify store must be in 'Connected' state to perform sync operations."))

        client = instance.get_api_client()
        feed_model = self.env["shopify.feed"]
        history_model = self.env["shopify.sync.history"]

        # Date formatting for Shopify ISO 8601
        updated_min_str = self.date_from.isoformat() if self.date_from else None

        if self.operation_type == "import":
            created_feeds = self.env["shopify.feed"]

            if self.entity_type == "order":
                orders_data = client.fetch_orders(limit=self.record_limit, updated_at_min=updated_min_str)
                for ord_data in orders_data:
                    ext_id = str(ord_data.get("id"))
                    order_num = ord_data.get("name") or ord_data.get("order_number") or ext_id
                    feed = feed_model.create({
                        "name": f"Shopify Order {order_num}",
                        "instance_id": instance.id,
                        "feed_type": "order",
                        "external_id": ext_id,
                        "raw_payload": json.dumps(ord_data),
                    })
                    created_feeds |= feed

                instance.last_order_sync = fields.Datetime.now()
                count = len(orders_data)
                history_model.create({
                    "name": f"Imported {count} Orders",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "order",
                    "status": "success",
                    "record_count": count,
                    "message": f"Successfully retrieved {count} orders from Shopify.",
                })

            elif self.entity_type == "product":
                products_data = client.fetch_products(limit=self.record_limit, updated_at_min=updated_min_str)
                for prod_data in products_data:
                    prod_data = self._attach_product_metafields(client, prod_data)
                    prod_data = self._attach_product_collections(client, prod_data)
                    ext_id = str(prod_data.get("id"))
                    title = prod_data.get("title") or f"Product #{ext_id}"
                    feed = feed_model.create({
                        "name": f"Shopify Product: {title}",
                        "instance_id": instance.id,
                        "feed_type": "product",
                        "external_id": ext_id,
                        "raw_payload": json.dumps(prod_data),
                    })
                    created_feeds |= feed

                instance.last_product_sync = fields.Datetime.now()
                count = len(products_data)
                history_model.create({
                    "name": f"Imported {count} Products",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "product",
                    "status": "success",
                    "record_count": count,
                    "message": f"Successfully retrieved {count} products from Shopify.",
                })

            elif self.entity_type == "category":
                collections_data = client.fetch_collections(limit=self.record_limit, updated_at_min=updated_min_str)
                for col_data in collections_data:
                    ext_id = str(col_data.get("id"))
                    title = col_data.get("title") or f"Collection #{ext_id}"
                    feed = feed_model.create({
                        "name": f"Shopify Category: {title}",
                        "instance_id": instance.id,
                        "feed_type": "category",
                        "external_id": ext_id,
                        "raw_payload": json.dumps(col_data),
                    })
                    created_feeds |= feed

                instance.last_category_sync = fields.Datetime.now()
                count = len(collections_data)
                history_model.create({
                    "name": f"Imported {count} Categories",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "category",
                    "status": "success",
                    "record_count": count,
                    "message": f"Successfully retrieved {count} collections/categories from Shopify.",
                })

            elif self.entity_type == "customer":
                customers_data = client.fetch_customers(limit=self.record_limit, updated_at_min=updated_min_str)
                for cust_data in customers_data:
                    ext_id = str(cust_data.get("id"))
                    name = f"{cust_data.get('first_name', '')} {cust_data.get('last_name', '')}".strip() or cust_data.get("email") or f"Customer #{ext_id}"
                    feed = feed_model.create({
                        "name": f"Shopify Customer: {name}",
                        "instance_id": instance.id,
                        "feed_type": "customer",
                        "external_id": ext_id,
                        "raw_payload": json.dumps(cust_data),
                    })
                    created_feeds |= feed

                instance.last_customer_sync = fields.Datetime.now()
                count = len(customers_data)
                history_model.create({
                    "name": f"Imported {count} Customers",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "customer",
                    "status": "success",
                    "record_count": count,
                    "message": f"Successfully retrieved {count} customers from Shopify.",
                })

            elif self.entity_type == "refund":
                order_maps = self.env["shopify.order.mapping"].search([
                    ("instance_id", "=", instance.id),
                ], limit=self.record_limit or 50, order="create_date desc")
                refund_count = 0
                for omap in order_maps:
                    try:
                        refunds_data = client.fetch_order_refunds(omap.shopify_order_id)
                        if refunds_data:
                            self.env["shopify.feed"]._process_order_refunds(
                                omap.order_id, omap.shopify_order_id, omap.shopify_order_number, refunds_data
                            )
                            refund_count += len(refunds_data)
                    except Exception as e:
                        _logger.warning("Failed to fetch refunds for Shopify Order #%s: %s", omap.shopify_order_number, str(e))

                history_model.create({
                    "name": f"Imported {refund_count} Order Refunds",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "order",
                    "status": "success",
                    "record_count": refund_count,
                    "message": f"Processed {refund_count} refunds across recent Shopify orders.",
                })

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Refunds Imported"),
                        "message": _("Processed %d refund record(s) from Shopify.") % refund_count,
                        "type": "success",
                        "sticky": False,
                    }
                }

            elif self.entity_type == "stock":
                if not feed_model._get_inventory_target_locations(instance):
                    raise UserError(_("No active location mappings found. Please discover or configure Shopify fulfillment locations first."))
                synced_count = feed_model._sync_inventory_from_shopify(
                    instance,
                    client=client,
                    limit=self.record_limit or 100,
                )

                instance.last_inventory_sync = fields.Datetime.now()
                history_model.create({
                    "name": f"Imported Inventory ({synced_count} items)",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "stock",
                    "status": "success",
                    "record_count": synced_count,
                    "message": f"Synchronized on-hand stock quantities for {synced_count} item(s) across mapped locations from Shopify.",
                })

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Inventory Imported"),
                        "message": _("Successfully updated stock levels for %d item(s) from Shopify.") % synced_count,
                        "type": "success",
                        "sticky": False,
                    }
                }

            elif self.entity_type == "metafield":
                fetched_count = instance.action_fetch_metafields(return_count=True)
                history_model.create({
                    "name": f"Fetched {fetched_count} Metafield Definitions",
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "metafield",
                    "status": "success",
                    "record_count": fetched_count,
                    "message": f"Fetched {fetched_count} Shopify metafield definition(s) into mapping configuration.",
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Metafields Fetched"),
                        "message": _("Fetched %d Shopify metafield definition(s).") % fetched_count,
                        "type": "success",
                        "sticky": False,
                    }
                }

            # Process feeds if toggled
            if self.auto_process_feed and created_feeds:
                created_feeds.action_process_feed()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Import Complete"),
                    "message": _("Successfully imported and staged %d %s record(s).") % (len(created_feeds), self.entity_type),
                    "type": "success",
                    "sticky": False,
                }
            }

        elif self.operation_type == "export":
            if self.entity_type == "stock":
                variant_maps = self.env["shopify.product.mapping"].search([
                    ("instance_id", "=", instance.id),
                    ("shopify_inventory_item_id", "!=", False),
                ])
                loc_maps = instance.location_mapping_ids.filtered(lambda l: l.sync_stock and l.active and l.location_id)
                synced_count = 0

                if loc_maps:
                    # Multi-location inventory push
                    for lmap in loc_maps:
                        for vmap in variant_maps:
                            qty = instance.get_stock_quantity(vmap.product_id, lmap.location_id)
                            try:
                                client.update_inventory_level(
                                    inventory_item_id=vmap.shopify_inventory_item_id,
                                    location_id=lmap.shopify_location_id,
                                    available_qty=qty,
                                )
                                synced_count += 1
                            except Exception as e:
                                _logger.warning("Failed to sync inventory for variant %s at location %s: %s", vmap.product_id.display_name, lmap.shopify_location_name, str(e))
                else:
                    if not instance.shopify_location_id:
                        raise UserError(_("Primary Shopify Location ID or Location Mapping is required to export inventory levels."))
                    stock_location = instance.location_id or (instance.warehouse_id.lot_stock_id if instance.warehouse_id else False)
                    for vmap in variant_maps:
                        qty = instance.get_stock_quantity(vmap.product_id, stock_location)
                        try:
                            client.update_inventory_level(
                                inventory_item_id=vmap.shopify_inventory_item_id,
                                location_id=instance.shopify_location_id,
                                available_qty=qty,
                            )
                            synced_count += 1
                        except Exception as e:
                            _logger.warning("Failed to sync inventory for variant %s: %s", vmap.product_id.display_name, str(e))

                instance.last_inventory_sync = fields.Datetime.now()
                history_model.create({
                    "name": f"Exported Inventory ({synced_count} items)",
                    "instance_id": instance.id,
                    "operation_type": "export",
                    "entity_type": "stock",
                    "status": "success",
                    "record_count": synced_count,
                    "message": f"Updated stock quantities for {synced_count} location-variant combination(s).",
                })

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Stock Exported"),
                        "message": _("Updated inventory levels for %d item(s) across mapped Shopify locations.") % synced_count,
                        "type": "success",
                        "sticky": False,
                    }
                }

            elif self.entity_type == "product":
                templates = self.env["product.template"].search([("sale_ok", "=", True)], limit=self.record_limit or 50)
                synced_count = 0
                metafield_count = 0
                for tmpl in templates:
                    mapping = self.env["shopify.template.mapping"].search([
                        ("instance_id", "=", instance.id),
                        ("template_id", "=", tmpl.id),
                    ], limit=1)
                    payload = self._prepare_shopify_product_payload(tmpl, template_mapping=mapping)
                    try:
                        if mapping:
                            client.update_product(mapping.shopify_product_id, payload)
                            shopify_product_id = mapping.shopify_product_id
                        else:
                            resp = client.create_product(payload)
                            sh_prod = resp.get("product", {})
                            shopify_product_id = str(sh_prod.get("id") or "")
                            new_variant_maps = self.env["shopify.product.mapping"]
                            if sh_prod.get("id"):
                                new_tmpl_map = self.env["shopify.template.mapping"].create({
                                    "instance_id": instance.id,
                                    "template_id": tmpl.id,
                                    "shopify_product_id": str(sh_prod["id"]),
                                    "shopify_handle": sh_prod.get("handle", ""),
                                })
                                for sh_var in sh_prod.get("variants", []):
                                    var_sku = sh_var.get("sku")
                                    matched_var = self._get_export_variant_for_shopify_options(tmpl, sh_var, self._get_export_option_lines(tmpl))
                                    if not matched_var and var_sku:
                                        matched_var = tmpl.product_variant_ids.filtered(lambda v: v.default_code == var_sku)[:1]
                                    if not matched_var:
                                        matched_var = tmpl.product_variant_ids[:1]
                                    if matched_var:
                                        new_map = self.env["shopify.product.mapping"].create({
                                            "instance_id": instance.id,
                                            "template_mapping_id": new_tmpl_map.id,
                                            "product_id": matched_var[0].id,
                                            "shopify_variant_id": str(sh_var["id"]),
                                            "shopify_sku": var_sku or "",
                                            "shopify_inventory_item_id": str(sh_var.get("inventory_item_id") or ""),
                                        })
                                        new_variant_maps |= new_map
                                mapping = new_tmpl_map
                                self._sync_initial_inventory_to_shopify(client, instance, new_variant_maps)
                        if shopify_product_id:
                            # Link product to its collections on Shopify
                            target_categories = tmpl.shopify_category_ids or tmpl.categ_id
                            for cat in target_categories:
                                cat_map = self.env["shopify.category.mapping"].search([
                                    ("instance_id", "=", instance.id),
                                    ("category_id", "=", cat.id),
                                ], limit=1)
                                if cat_map and cat_map.shopify_collection_id and not cat_map.shopify_collection_id.startswith("type_"):
                                    try:
                                        client.add_product_to_collection(shopify_product_id, cat_map.shopify_collection_id)
                                    except Exception as e:
                                        _logger.info("Collection link for %s to %s: %s", shopify_product_id, cat_map.shopify_collection_id, str(e))
                            metafield_count += self._push_metafields(
                                client,
                                "products",
                                shopify_product_id,
                                self._collect_record_metafields(tmpl, "product.template", instance),
                            )
                        variant_maps = self.env["shopify.product.mapping"].search([
                            ("instance_id", "=", instance.id),
                            ("template_mapping_id", "=", mapping.id),
                            ("shopify_variant_id", "!=", False),
                        ]) if mapping else self.env["shopify.product.mapping"]
                        for variant_map in variant_maps:
                            metafield_count += self._push_metafields(
                                client,
                                "variants",
                                variant_map.shopify_variant_id,
                                self._collect_record_metafields(variant_map.product_id, "product.product", instance),
                            )
                        synced_count += 1
                    except Exception as e:
                        _logger.warning("Failed to export product %s to Shopify: %s", tmpl.name, str(e))

                instance.last_product_sync = fields.Datetime.now()
                history_model.create({
                    "name": f"Exported {synced_count} Products",
                    "instance_id": instance.id,
                    "operation_type": "export",
                    "entity_type": "product",
                    "status": "success",
                    "record_count": synced_count,
                    "message": f"Successfully exported/updated {synced_count} products and {metafield_count} metafields on Shopify.",
                })

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Products Exported"),
                        "message": _("Successfully exported %d product(s) and %d metafield value(s) to Shopify.") % (synced_count, metafield_count),
                        "type": "success",
                        "sticky": False,
                    }
                }

            elif self.entity_type == "category":
                # Find categories not yet mapped as collections (custom/smart)
                mapped_categ_ids = self.env["shopify.category.mapping"].search([
                    ("instance_id", "=", instance.id),
                    ("shopify_collection_type", "in", ("custom", "smart")),
                ]).mapped("category_id.id")
                categories = self.env["product.category"].search([
                    ("id", "not in", mapped_categ_ids),
                ], limit=self.record_limit or 50)
                synced_count = 0
                for categ in categories:
                    mapping = self.env["shopify.category.mapping"].search([
                        ("instance_id", "=", instance.id),
                        ("category_id", "=", categ.id),
                    ], limit=1)
                    payload = {
                        "title": categ.name,
                    }
                    try:
                        resp = client.create_collection(payload)
                        col = resp.get("custom_collection", {})
                        if col.get("id"):
                            if mapping:
                                mapping.write({
                                    "shopify_collection_id": str(col["id"]),
                                    "shopify_collection_title": col.get("title", categ.name),
                                    "shopify_handle": col.get("handle", ""),
                                    "shopify_collection_type": "custom",
                                })
                            else:
                                self.env["shopify.category.mapping"].create({
                                    "instance_id": instance.id,
                                    "category_id": categ.id,
                                    "shopify_collection_id": str(col["id"]),
                                    "shopify_collection_title": col.get("title", categ.name),
                                    "shopify_handle": col.get("handle", ""),
                                    "shopify_collection_type": "custom",
                                })
                            synced_count += 1
                    except Exception as e:
                        _logger.warning("Failed to export category %s to Shopify: %s", categ.name, str(e))

                instance.last_category_sync = fields.Datetime.now()
                history_model.create({
                    "name": f"Exported {synced_count} Categories",
                    "instance_id": instance.id,
                    "operation_type": "export",
                    "entity_type": "category",
                    "status": "success",
                    "record_count": synced_count,
                    "message": f"Successfully exported/updated {synced_count} categories to Shopify custom collections.",
                })

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Categories Exported"),
                        "message": _("Successfully exported %d category(ies) to Shopify collections.") % synced_count,
                        "type": "success",
                        "sticky": False,
                    }
                }
            else:
                raise UserError(_("Export operation is currently supported for 'Products & Variants', 'Categories / Collections', and 'Inventory Quantities'."))

        return {"type": "ir.actions.act_window_close"}
