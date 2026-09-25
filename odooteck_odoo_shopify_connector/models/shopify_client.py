# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import json
import time
import logging
import requests
from urllib.parse import urlparse
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ShopifyNotFoundError(UserError):
    """Raised when a Shopify resource is not found (HTTP 404), e.g. deleted on Shopify."""
    pass

class ShopifyApiClient:
    """
    Robust, standalone HTTP client for the Shopify Admin REST API.
    Provides automated rate-limit handling (HTTP 429), token-based authentication,
    and unified serialization for eCommerce synchronization.
    """

    DEFAULT_API_VERSION = "2025-01"

    def __init__(self, shop_url, access_token, api_version=None, timeout=30):
        self.shop_url = self._normalize_shop_url(shop_url)
        self.access_token = (access_token or "").strip()
        self.api_version = api_version or self.DEFAULT_API_VERSION
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Shopify-Access-Token": self.access_token,
        })

    @staticmethod
    def _normalize_shop_url(url):
        if not url:
            return ""
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path
        return f"https://{netloc.rstrip('/')}"

    def _get_api_endpoint(self, path):
        clean_path = path.lstrip("/")
        return f"{self.shop_url}/admin/api/{self.api_version}/{clean_path}"

    def _execute_request(self, method, path, params=None, data=None, max_retries=3):
        url = self._get_api_endpoint(path)
        payload = json.dumps(data) if data and isinstance(data, dict) else data

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=payload,
                    timeout=self.timeout,
                )

                # Rate limiting handler (Shopify REST Leaky Bucket)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 2.0))
                    _logger.warning(
                        "Shopify API rate limit encountered (429). Retrying in %s seconds (Attempt %s/%s)...",
                        retry_after, attempt, max_retries
                    )
                    time.sleep(retry_after)
                    continue

                if response.status_code in (200, 201):
                    return response.json() if response.content else {}

                if response.status_code == 204:
                    return {}

                if response.status_code == 404:
                    error_msg = f"Shopify API Error (404 Not Found) on {method.upper()} {path}: {response.text}"
                    _logger.warning(error_msg)
                    raise ShopifyNotFoundError(error_msg)

                # Detailed error formatting
                error_msg = f"Shopify API Error ({response.status_code}) on {method.upper()} {path}: {response.text}"
                _logger.error(error_msg)
                raise UserError(error_msg)

            except requests.exceptions.RequestException as e:
                _logger.error("Network communication error with Shopify API (%s): %s", url, str(e))
                if attempt == max_retries:
                    raise UserError(f"Failed to communicate with Shopify API after {max_retries} attempts: {str(e)}")
                time.sleep(1.5 * attempt)

        raise UserError(f"Request to Shopify failed after {max_retries} retries due to rate limiting or connection issues.")

    def _execute_graphql(self, query, variables=None, max_retries=3):
        payload = {"query": query, "variables": variables or {}}
        return self._execute_request("POST", "graphql.json", data=payload, max_retries=max_retries)

    # -------------------------------------------------------------------------
    # Core API Operations
    # -------------------------------------------------------------------------

    def test_connection(self):
        """Verifies access token and store URL by querying shop metadata."""
        data = self._execute_request("GET", "shop.json")
        return data.get("shop", {})

    def get_locations(self):
        """Fetches active inventory fulfillment locations."""
        data = self._execute_request("GET", "locations.json")
        return data.get("locations", [])

    def fetch_products(self, limit=50, since_id=None, updated_at_min=None):
        """Retrieves products from the store."""
        params = {"limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        if updated_at_min:
            params["updated_at_min"] = updated_at_min

        data = self._execute_request("GET", "products.json", params=params)
        return data.get("products", [])

    def fetch_product(self, shopify_product_id):
        """Retrieves a single product by Shopify product ID."""
        data = self._execute_request("GET", f"products/{shopify_product_id}.json")
        return data.get("product", {})

    def delete_product(self, shopify_product_id):
        """Deletes a product from Shopify."""
        return self._execute_request("DELETE", f"products/{shopify_product_id}.json")

    def fetch_orders(self, limit=50, status="any", financial_status=None, fulfillment_status=None, since_id=None, updated_at_min=None):
        """Retrieves orders matching the specified filter criteria."""
        params = {"limit": min(limit, 250), "status": status}
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status
        if since_id:
            params["since_id"] = since_id
        if updated_at_min:
            params["updated_at_min"] = updated_at_min

        data = self._execute_request("GET", "orders.json", params=params)
        return data.get("orders", [])

    def fetch_customers(self, limit=50, since_id=None, updated_at_min=None):
        """Retrieves registered customer profiles."""
        params = {"limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        if updated_at_min:
            params["updated_at_min"] = updated_at_min

        data = self._execute_request("GET", "customers.json", params=params)
        return data.get("customers", [])

    def fetch_inventory_levels(self, location_ids=None, inventory_item_ids=None, limit=50):
        """Retrieves inventory levels for specified locations or inventory items."""
        params = {"limit": min(limit, 250)}
        if location_ids:
            if isinstance(location_ids, (list, tuple)):
                params["location_ids"] = ",".join(str(lid) for lid in location_ids)
            else:
                params["location_ids"] = str(location_ids)
        if inventory_item_ids:
            if isinstance(inventory_item_ids, (list, tuple)):
                params["inventory_item_ids"] = ",".join(str(item_id) for item_id in inventory_item_ids)
            else:
                params["inventory_item_ids"] = str(inventory_item_ids)

        data = self._execute_request("GET", "inventory_levels.json", params=params)
        return data.get("inventory_levels", [])

    def update_inventory_level(self, inventory_item_id, location_id, available_qty):
        """Sets inventory quantity for an item at a specific location."""
        payload = {
            "location_id": int(location_id),
            "inventory_item_id": int(inventory_item_id),
            "available": int(available_qty),
        }
        return self._execute_request("POST", "inventory_levels/set.json", data=payload)

    def create_fulfillment(self, order_id, tracking_number=None, tracking_company=None, tracking_url=None, line_items=None):
        """Submits fulfillment and tracking data for an order."""
        fulfillment_dict = {
            "notify_customer": True,
        }
        if tracking_number:
            fulfillment_dict["tracking_number"] = tracking_number
        if tracking_company:
            fulfillment_dict["tracking_company"] = tracking_company
        if tracking_url:
            fulfillment_dict["tracking_url"] = tracking_url
        if line_items:
            fulfillment_dict["line_items_by_fulfillment_order"] = line_items

        payload = {"fulfillment": fulfillment_dict}
        return self._execute_request("POST", f"orders/{order_id}/fulfillments.json", data=payload)

    def create_product(self, product_data):
        """Creates a new product on Shopify."""
        payload = {"product": product_data}
        return self._execute_request("POST", "products.json", data=payload)

    def update_product(self, shopify_product_id, product_data):
        """Updates an existing product on Shopify."""
        payload = {"product": product_data}
        return self._execute_request("PUT", f"products/{shopify_product_id}.json", data=payload)

    def fetch_metafields(self, resource_type, resource_id):
        """Fetches metafields for a given resource (e.g. products, customers, orders)."""
        data = self._execute_request("GET", f"{resource_type}/{resource_id}/metafields.json")
        return data.get("metafields", [])

    def fetch_metafield_definitions(self, owner_types=None, limit=100):
        """Fetches Shopify metafield definitions via GraphQL."""
        owner_types = owner_types or ["PRODUCT", "PRODUCTVARIANT", "CUSTOMER", "ORDER"]
        query = """
            query GetMetafieldDefinitions($ownerType: MetafieldOwnerType!, $first: Int!, $after: String) {
                metafieldDefinitions(ownerType: $ownerType, first: $first, after: $after) {
                    nodes {
                        id
                        name
                        namespace
                        key
                        description
                        ownerType
                        type {
                            name
                            category
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        """
        definitions = []
        for owner_type in owner_types:
            after = None
            while True:
                response = self._execute_graphql(query, {
                    "ownerType": owner_type,
                    "first": min(limit or 100, 250),
                    "after": after,
                })
                if response.get("errors"):
                    raise UserError("Shopify GraphQL Error: %s" % response.get("errors"))
                data = (response.get("data") or {}).get("metafieldDefinitions") or {}
                for definition in data.get("nodes") or []:
                    definition["ownerType"] = definition.get("ownerType") or owner_type
                    definitions.append(definition)
                page_info = data.get("pageInfo") or {}
                if not page_info.get("hasNextPage"):
                    break
                after = page_info.get("endCursor")
        return definitions

    def set_metafield(self, resource_type, resource_id, metafield_data):
        """Creates or updates a metafield on a given resource."""
        namespace = metafield_data.get("namespace") or "custom"
        key = metafield_data.get("key")
        if key:
            for metafield in self.fetch_metafields(resource_type, resource_id):
                if metafield.get("namespace") == namespace and metafield.get("key") == key and metafield.get("id"):
                    payload = {"metafield": dict(metafield_data, id=metafield.get("id"))}
                    return self._execute_request(
                        "PUT",
                        f"{resource_type}/{resource_id}/metafields/{metafield.get('id')}.json",
                        data=payload,
                    )
        payload = {"metafield": metafield_data}
        return self._execute_request("POST", f"{resource_type}/{resource_id}/metafields.json", data=payload)

    def fetch_order_refunds(self, order_id):
        """Retrieves all refund records for a specific order."""
        data = self._execute_request("GET", f"orders/{order_id}/refunds.json")
        return data.get("refunds", [])

    def get_inventory_levels(self, location_ids=None, inventory_item_ids=None):
        """Retrieves inventory levels for specific locations or inventory items."""
        params = {}
        if location_ids:
            params["location_ids"] = ",".join(str(l) for l in location_ids) if isinstance(location_ids, list) else str(location_ids)
        if inventory_item_ids:
            params["inventory_item_ids"] = ",".join(str(i) for i in inventory_item_ids) if isinstance(inventory_item_ids, list) else str(inventory_item_ids)
        data = self._execute_request("GET", "inventory_levels.json", params=params)
        return data.get("inventory_levels", [])

    # -------------------------------------------------------------------------
    # Category / Collection Operations
    # -------------------------------------------------------------------------

    def fetch_collections(self, limit=50, updated_at_min=None):
        """Retrieves both custom and smart collections from the store."""
        params = {"limit": min(limit, 250)}
        if updated_at_min:
            params["updated_at_min"] = updated_at_min

        collections = []
        # 1. Custom Collections
        try:
            custom_data = self._execute_request("GET", "custom_collections.json", params=params)
            for col in custom_data.get("custom_collections", []):
                col["collection_type"] = "custom"
                collections.append(col)
        except Exception as e:
            _logger.warning("Failed to fetch custom collections: %s", str(e))

        # 2. Smart Collections
        try:
            smart_data = self._execute_request("GET", "smart_collections.json", params=params)
            for col in smart_data.get("smart_collections", []):
                col["collection_type"] = "smart"
                collections.append(col)
        except Exception as e:
            _logger.warning("Failed to fetch smart collections: %s", str(e))

        return collections

    def fetch_collection(self, collection_id):
        """Retrieves a single collection by ID (checking custom then smart)."""
        try:
            data = self._execute_request("GET", f"custom_collections/{collection_id}.json")
            col = data.get("custom_collection")
            if col:
                col["collection_type"] = "custom"
                return col
        except Exception:
            pass

        try:
            data = self._execute_request("GET", f"smart_collections/{collection_id}.json")
            col = data.get("smart_collection")
            if col:
                col["collection_type"] = "smart"
                return col
        except Exception:
            pass
        return {}

    def fetch_collects(self, product_id=None, collection_id=None, limit=250):
        """Retrieves product-collection links from Shopify."""
        params = {"limit": min(limit, 250)}
        if product_id:
            params["product_id"] = product_id
        if collection_id:
            params["collection_id"] = collection_id

        data = self._execute_request("GET", "collects.json", params=params)
        return data.get("collects", [])

    def create_collection(self, collection_data):
        """Creates a new custom collection on Shopify."""
        payload = {"custom_collection": collection_data}
        return self._execute_request("POST", "custom_collections.json", data=payload)

    def update_collection(self, collection_id, collection_data):
        """Updates an existing custom collection on Shopify."""
        payload = {"custom_collection": collection_data}
        return self._execute_request("PUT", f"custom_collections/{collection_id}.json", data=payload)

    def add_product_to_collection(self, product_id, collection_id):
        """Links a product to a custom collection on Shopify."""
        payload = {
            "collect": {
                "product_id": int(product_id),
                "collection_id": int(collection_id),
            }
        }
        return self._execute_request("POST", "collects.json", data=payload)

    def remove_product_from_collection(self, collect_id):
        """Removes a product from a collection via its collect ID."""
        return self._execute_request("DELETE", f"collects/{collect_id}.json")
