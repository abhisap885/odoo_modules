# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

{
    "name": "Shopify Odoo Connector | All-in-One Multi-Store Shopify Integration",
    "summary": "Shopify Odoo Connector for Odoo 19: Real-time stock sync, automated webhook order import, staging feeds queue, multi-store & multi-company, bi-directional product variants mapping, auto-invoicing, zero dependencies.",
    "description": """
Shopify Odoo Connector — Enterprise Edition (Odoo 19)
=====================================================
The most powerful, lossless, and standalone Shopify integration engineered specifically for Odoo 19.

Key Integration Highlights:
---------------------------
* Direct Shopify Admin REST & GraphQL API integration (100% standalone, zero 3rd-party dependencies).
* Multi-Store & Multi-Company: Connect and manage unlimited Shopify storefronts with strict multi-company segregation.
* Resilient Staging Feeds Queue (`shopify.feed`): Lossless buffer for incoming webhooks and batch syncs.
* Real-Time Bi-Directional Stock Sync: Instant stock updates from Odoo warehouses to Shopify locations with loop-prevention guards.
* Automated Order-to-Cash Reconciliation: Automatic confirmation, customer matching, tax mapping, invoice generation, and bank payment reconciliation.
* Product & Matrix Variant Mapping: Full bi-directional sync with 1-click Push/Pull on product forms and automatic HTTP 404 delete detection.
* Comprehensive Audit Trail: Full API payload logging, sync history, error traces, and customer mapping directory.
* Native Odoo 19 3-Tier Security model (`res.groups.privilege`).

Compatible with Odoo 19.0 Community, Enterprise, Odoo.sh, and On-Premise.
    """,
    "author": "Odooteck",
    "category": "eCommerce",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "depends": [
        "base",
        "sale_management",
        "stock",
        "account",
    ],
    "data": [
        # 1. Security (Privileges, Groups, Access Control Lists)
        "security/security.xml",
        "security/ir.model.access.csv",

        # 2. System Data & Scheduled Actions
        "data/data.xml",
        "data/cron.xml",

        # 3. Wizards (loaded before views referencing wizard actions)
        "views/shopify_sync_wizard_views.xml",
        "views/shopify_product_export_wizard_views.xml",
        "views/shopify_onboarding_wizard_views.xml",
        "views/shopify_store_create_wizard_views.xml",

        # 4. Core Views
        "views/shopify_instance_views.xml",
        "views/shopify_feed_views.xml",
        "views/shopify_mapping_views.xml",
        "views/shopify_sync_history_views.xml",
        "views/inherited_views.xml",

        # 5. Menus (Hierarchy & Actions)
        "views/menus.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odooteck_odoo_shopify_connector/static/src/scss/shopify_kanban.scss",
            "odooteck_odoo_shopify_connector/static/src/scss/shopify_insights.scss",
            "odooteck_odoo_shopify_connector/static/src/js/shopify_insights_dashboard.js",
            "odooteck_odoo_shopify_connector/static/src/xml/shopify_insights_dashboard.xml",
        ],
    },
    "images": ["static/description/banner.png", "static/description/sync_flow.gif"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
}
