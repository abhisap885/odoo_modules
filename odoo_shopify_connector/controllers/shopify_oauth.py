# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import hmac
import hashlib
import logging
from urllib.parse import urlencode
import werkzeug
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class ShopifyOAuthController(http.Controller):

    def _verify_oauth_hmac(self, client_secret, received_hmac, query_params):
        """Verifies HMAC signature sent by Shopify on OAuth callback."""
        if not client_secret or not received_hmac:
            return False
        # Shopify requires calculating HMAC across all GET query parameters except 'hmac' and 'signature'
        filtered_params = {k: v for k, v in query_params.items() if k not in ("hmac", "signature")}
        query_string = urlencode(sorted(filtered_params.items()))
        computed_hash = hmac.new(
            client_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_hash, received_hmac)

    @http.route(
        "/shopify/oauth/callback",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def shopify_oauth_callback(self, **kwargs):
        """
        Callback handler invoked by Shopify after merchant authorizes the application.
        Verifies HMAC, exchanges code for access token, and redirects merchant back to Odoo.
        """
        instance_id = kwargs.get("state")
        code = kwargs.get("code")
        shop = kwargs.get("shop")
        received_hmac = kwargs.get("hmac")

        if not instance_id or not code:
            _logger.error("Shopify OAuth callback missing required parameters: %s", kwargs)
            return Response("Missing required parameters (code or state).", status=400)

        instance = request.env["shopify.instance"].sudo().browse(int(instance_id))
        if not instance.exists():
            _logger.error("Shopify instance with ID %s not found", instance_id)
            return Response("Invalid Store Instance", status=404)

        # Verify HMAC signature
        if instance.client_secret:
            if not self._verify_oauth_hmac(instance.client_secret, received_hmac, kwargs):
                _logger.error("Shopify OAuth HMAC verification failed for instance %s", instance.name)
                return Response("Invalid HMAC Signature", status=403)

        # Exchange code for access token
        try:
            instance.connect_with_oauth_code(code, shop)
        except Exception as e:
            _logger.exception("Failed to exchange OAuth code for token: %s", str(e))
            instance.write({"state": "error"})
            return Response(f"OAuth connection failed: {str(e)}", status=500)

        # Redirect user back to Odoo backend instance form view
        action = request.env.ref("odoo_shopify_connector.action_shopify_instance", raise_if_not_found=False)
        action_id = action.id if action else ""
        redirect_url = f"/web#id={instance.id}&cids=1&model=shopify.instance&view_type=form"
        if action_id:
            redirect_url += f"&action={action_id}"
        return werkzeug.utils.redirect(redirect_url)
