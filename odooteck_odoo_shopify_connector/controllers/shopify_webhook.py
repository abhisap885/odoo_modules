# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import hmac
import hashlib
import base64
import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class ShopifyWebhookController(http.Controller):

    def _verify_webhook_signature(self, data_bytes, secret, received_hmac):
        """Verifies incoming payload against Shopify HMAC-SHA256 signature header."""
        if not secret or not received_hmac:
            return False
        computed_hash = hmac.new(
            secret.encode("utf-8"),
            data_bytes,
            hashlib.sha256
        ).digest()
        computed_hmac = base64.b64encode(computed_hash).decode("utf-8")
        return hmac.compare_digest(computed_hmac, received_hmac)

    @http.route(
        "/shopify/webhook/<int:instance_id>/<string:topic>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def handle_shopify_webhook(self, instance_id, topic, **kwargs):
        """
        Receives real-time events from Shopify (e.g. orders_create, orders_updated, products_update).
        Stages payload in shopify.feed and triggers automatic synchronization.
        """
        instance = request.env["shopify.instance"].sudo().browse(instance_id)
        if not instance.exists() or instance.state != "confirmed":
            _logger.warning("Webhook received for non-existent or inactive Shopify instance %s", instance_id)
            return Response("Invalid Store Instance", status=404)

        raw_data = request.httprequest.get_data()
        received_hmac = request.httprequest.headers.get("X-Shopify-Hmac-Sha256")

        # Optional signature verification if secret is configured
        if instance.webhook_secret:
            if not self._verify_webhook_signature(raw_data, instance.webhook_secret, received_hmac):
                _logger.error("Shopify Webhook HMAC verification failed for instance %s, topic %s", instance.name, topic)
                return Response("Unauthorized Signature", status=401)

        try:
            payload = json.loads(raw_data.decode("utf-8"))
        except Exception as e:
            _logger.error("Failed to decode JSON webhook payload: %s", str(e))
            return Response("Malformed JSON", status=400)

        ext_id = str(payload.get("id"))

        # Dedicated handler for direct refund webhooks
        if "refund" in topic:
            order_id = str(payload.get("order_id") or "")
            order_map = request.env["shopify.order.mapping"].sudo().search([
                ("instance_id", "=", instance.id),
                ("shopify_order_id", "=", order_id),
            ], limit=1)
            if order_map:
                request.env["shopify.feed"].sudo()._process_order_refunds(
                    order_map.order_id, order_id, order_map.shopify_order_number, [payload]
                )
            feed_type = "order"
        elif "product" in topic and "delete" in topic:
            tmpl_map = request.env["shopify.template.mapping"].sudo().search([
                ("instance_id", "=", instance.id),
                ("shopify_product_id", "=", ext_id),
            ], limit=1)
            if tmpl_map:
                tmpl_map.write({
                    "shopify_status": "deleted",
                    "is_deleted_on_shopify": True,
                })
            feed_type = "product"
        else:
            feed_type = "order" if "order" in topic else ("product" if "product" in topic else "customer")

        feed = request.env["shopify.feed"].sudo().create({
            "name": f"Webhook [{topic}] #{ext_id}",
            "instance_id": instance.id,
            "feed_type": feed_type,
            "external_id": ext_id,
            "raw_payload": json.dumps(payload),
        })

        # Process feed immediately if not already handled
        if "refund" not in topic and not ("product" in topic and "delete" in topic):
            feed.action_process_feed()
        else:
            feed.write({"state": "done"})

        # Log history
        request.env["shopify.sync.history"].sudo().create({
            "name": f"Webhook Triggered: {topic}",
            "instance_id": instance.id,
            "operation_type": "webhook",
            "entity_type": feed_type,
            "status": "success",
            "record_count": 1,
            "message": f"Processed webhook for external ID {ext_id} under topic '{topic}'.",
        })

        return Response("Webhook Accepted", status=200)
