# Shopify Odoo Connector (Odoo 19)

[![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue.svg)](https://www.odoo.com)
[![License](https://img.shields.io/badge/License-OPL--1-blue.svg)](LICENSE)
![Author](https://img.shields.io/badge/Author-Odooteck-orange.svg)

**Shopify Odoo Connector** is a modern, standalone, enterprise-grade integration bridge connecting one or multiple Shopify stores with **Odoo 19**. Developed strictly adhering to modern Odoo 19 architecture standards, it communicates directly with the **Shopify Admin GraphQL API** without requiring third-party middleware, external subscription services, or proprietary dependencies.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture & Standards](#architecture--standards)
- [Prerequisites & Compatibility](#prerequisites--compatibility)
- [Installation Guide](#installation-guide)
- [Configuration Walkthrough](#configuration-walkthrough)
  - [1. Generate Shopify Admin API Credentials](#1-generate-shopify-admin-api-credentials)
  - [2. Configure Shopify Store in Odoo](#2-configure-shopify-store-in-odoo)
  - [3. Test Connection & Discover Locations](#3-test-connection--discover-locations)
- [User Guide & Operations](#user-guide--operations)
  - [Multi-Location Stock Mapping & Sync (Import & Export)](#multi-location-stock-mapping--sync-import--export)
  - [Declarative Metafields Mapping Engine](#declarative-metafields-mapping-engine)
  - [Automated Order Refund & Return Management](#automated-order-refund--return-management)
  - [Manual Sync Wizard](#manual-sync-wizard)
  - [Staging Feeds (Lossless Queue)](#staging-feeds-lossless-queue)
  - [Bi-directional Mapping System](#bi-directional-mapping-system)
  - [Automated Real-time Delivery Fulfillment](#automated-real-time-delivery-fulfillment)
  - [Scheduled Automation (Cron Jobs)](#scheduled-automation-cron-jobs)
  - [Real-Time Webhooks Setup](#real-time-webhooks-setup)
  - [Audit & Sync History Logs](#audit--sync-history-logs)
- [Technical Architecture & Models](#technical-architecture--models)
- [Troubleshooting & FAQs](#troubleshooting--faqs)
- [Copyright & Licensing](#copyright--licensing)

---

## Key Features

- **Multi-Store Management**: Connect unlimited Shopify storefronts to a single Odoo instance. Each store can have independent warehouses, sales teams, pricelists, and currency configurations.
- **Resilient Staging Queue (Feeds)**: Data imported from Shopify (Orders, Products, Customers) is staged in `shopify.feed` queues before processing into core Odoo records, eliminating data loss during network hiccups or schema changes.
- **Multi-Location Inventory Management (Import & Export)**:
  - Synchronize stock levels between individual Shopify fulfillment locations and corresponding Odoo warehouses/stock locations.
  - Export on-hand inventory levels from designated Odoo stock locations to Shopify locations.
  - Import live Shopify inventory levels into Odoo stock locations using automated stock adjustments (`stock.quant`).
  - Automatic warehouse and delivery picking routing based on the Shopify fulfillment location of imported orders.
- **Declarative Metafields Engine**:
  - Dynamically map custom Shopify metafields (namespace & key) to native or custom Odoo fields across `product.template`, `product.product`, `res.partner`, and `sale.order`.
  - Supports multiple data types: Single-Line Text, Multi-Line Text, Integer, Decimal, Boolean, JSON, and URL.
  - Configurable synchronization direction: Bidirectional, Import Only, or Export Only.
- **Automated Order Refund & Return Management**:
  - Automatically or manually ingest order refunds from Shopify via webhooks and the Sync Wizard.
  - Automatically create customer Credit Notes (`account.move` of type `out_refund`) linked to original sales orders.
  - Flexible automation toggles: Auto-Process Refunds, Auto-Create Credit Notes, and Auto-Post Credit Notes.
- **Bi-directional Product & Variant Sync**:
  - Export Odoo products and variants (including SKU, barcode, pricing, descriptions, and metafields) to Shopify.
  - Import Shopify products, variants, and URL handles into Odoo with automated SKU-based mapping.
- **Order Lifecycle Automation**:
  - Fetch pending, open, and fulfilled orders.
  - Automatic customer matching (by email/Shopify Customer ID) or new partner creation.
  - Line items, shipping charges, discount codes, and taxes mapped automatically.
  - Optional auto-confirmation of Sales Orders and automated Customer Invoice generation.
- **Automated Delivery Tracking (Fulfillment Push)**:
  - When a delivery order (`stock.picking`) is validated in Odoo, tracking numbers and carrier details are instantly dispatched to Shopify, automatically marking the order as fulfilled on the store.
- **Secure Webhook Ingestion**:
  - Built-in HTTP controller with cryptographic **HMAC-SHA256 signature verification** for Shopify webhooks (`orders_create`, `orders_updated`, `products_create`, `products_update`, `customers_create`, `refunds_create`).
- **Full Odoo 19 Compliance**:
  - Modern declarative constraints (`models.Constraint`).
  - Native `<list>` views (replacing deprecated `<tree>` tags).
  - Strict 3-Tier Security model (`ir.module.category` -> `res.groups.privilege` -> `res.groups`).

---

## Architecture & Standards

| Component | Standard Implemented |
| :--- | :--- |
| **Odoo Framework** | Odoo 19.0 (Community & Enterprise) |
| **Python Runtime** | Python 3.10+ (tested on Python 3.12) |
| **Shopify API** | Shopify Admin GraphQL API |
| **Security Architecture** | Odoo 19 3-tier model with `res.groups.privilege` |
| **View Engine** | Native `<list>` views & modern Python domain expressions (`invisible="..."`) |
| **Data Integrity** | `models.Constraint` declarative SQL unique indices |

---

## Prerequisites & Compatibility

- **Odoo**: Version 19.0
- **Required Core Modules**:
  - `sale_management`
  - `stock`
  - `account`
- **Shopify Plan**: Any plan supporting Custom Apps with Admin API access (Shopify Basic, Shopify, Advanced, Shopify Plus).
- **Python Libraries**: `requests`, `urllib3` (standard in standard Odoo environments).

---

## Installation Guide

1. **Place the Module**:
   Ensure the `odooteck_odoo_shopify_connector` directory is located in your custom Odoo addons path:
   ```text
   C:\odoosetup19\odooteck_odoo_shopify_connector
   ```

2. **Update Addons Path**:
   Ensure your `odoo.conf` file includes the custom addons directory in `addons_path`:
   ```ini
   addons_path = /opt/odoo/addons,/opt/odoo/odoo/addons,/opt/odoo-custom-addons
   ```

3. **Install the Module**:
   - Activate **Developer Mode** in Odoo (`Settings` -> `General Settings` -> `Activate developer mode`).
   - Go to **Apps** -> **Update Apps List**.
   - Search for **Shopify Odoo Connector**.
   - Click **Activate / Install**.

---

## Configuration Walkthrough

The connector supports two flexible authentication modes:
- **Method A (Recommended for Partner / Multi-Merchant Apps)**: **Shopify OAuth 2.0 (1-Click Redirect)** – Enter Client ID and Secret, click **Connect via Shopify OAuth**, and approve in Shopify. Odoo securely completes the OAuth handshake and auto-fills credentials.
- **Method B (For Private / In-Store Custom Apps)**: **Direct Admin API Access Token** – Generate a Custom App directly in Shopify Store Admin and paste the `shpat_...` access token.

---

### 1. Authentication Setup

#### Method A: Shopify OAuth 2.0 (1-Click Redirect)
1. In your **Shopify Partner Dashboard** (or Shopify App Configuration):
   - Under App Setup, find your **Client ID** (API Key) and **Client Secret**.
   - Add the **OAuth Redirect URI** shown in your Odoo store form to your Shopify App's **Allowed redirection URL(s)**:
     ```text
     https://<your-odoo-domain>/shopify/oauth/callback
     ```
2. In Odoo:
   - On the Shopify Store form under **API & Authentication**, select **Authentication Method = Shopify OAuth 2.0 (1-Click Redirect)**.
   - Enter your **Store URL**, **Client ID**, and **Client Secret**.
   - Click **Save**, then click the **Connect via Shopify OAuth** button in the header.
   - Your browser redirects to Shopify's consent screen. Click **Install App / Authorize**.
   - Shopify automatically redirects back to Odoo with HMAC verification, retrieves the permanent access token, and sets the store to **Connected**!

#### Method B: Direct Admin API Token (Custom App)
1. Log in to your **Shopify Store Admin** (`https://admin.shopify.com/store/<your-store>`).
2. Navigate to **Settings** &rarr; **Apps and sales channels** &rarr; **Develop apps**.
3. Click **Create an app** and give it a name (e.g., `Odoo 19 Integration`).
4. Under **Configuration** &rarr; **Admin API integration**, enable the necessary scopes (`read_products`, `write_products`, `read_orders`, `write_orders`, `read_customers`, `write_customers`, `read_inventory`, `write_inventory`, `read_fulfillments`, `write_fulfillments`, `read_locations`).
5. Click **Save** and then click **Install app**.
6. Reveal and copy the **Admin API access token** (starts with `shpat_...`).
7. In Odoo, select **Authentication Method = Direct Admin API Token**, paste the token, and click **Connect & Test**.

---

### 2. Configure Store Defaults in Odoo

In Odoo, configure operational defaults on the instance record:

| Field | Description | Example |
| :--- | :--- | :--- |
| **Store Name** | A friendly internal reference | `My Main Store` |
| **Store URL** | Primary `myshopify.com` domain | `https://my-store.myshopify.com` |
| **API Version** | Shopify API Version | `Latest Stable` |
| **Default Warehouse** | Odoo warehouse for order fulfillment | `San Francisco / WH` |
| **Company** | Multi-company assignment | `Your Company` |
| **Sales Team** | Sales channel assignment | `Website Sales` |
| **Pricelist** | Target pricelist for currency & rates | `Public Pricelist (USD)` |
| **Discount Service Product** | Generic service product for line discounts | `Discount` |
| **Shipping Charge Product** | Product used to represent delivery costs | `Delivery Charges` |

---

### 3. Test Connection & Discover Locations

1. If connecting via Direct Token, click **Connect & Test** in the header.
2. If connecting via OAuth, click **Connect via Shopify OAuth**.
3. The connector verifies API credentials, retrieves store information, and activates the store into `Connected` state.
4. Click **Discover Locations** in the header or open the **Locations** tab. The connector automatically fetches all Shopify fulfillment locations and maps them into Odoo.

---

## User Guide & Operations

### Multi-Location Stock Mapping & Sync (Import & Export)

The connector features multi-location inventory synchronization allowing different Shopify locations to map directly to specific Odoo Warehouses and internal stock locations:

1. **Configure Locations**:
   - Open your Store Instance and navigate to the **Locations** tab (or via **Mappings** &rarr; **Locations**).
   - Each discovered Shopify location can be assigned to an **Odoo Warehouse** and a specific **Internal Stock Location**.
   - Toggle **Sync Stock** to enable or disable inventory sync for individual locations.
   - Designate one location as the **Primary Location**.
2. **Export Stock to Shopify by Location**:
   - In the **Sync Wizard**, select `Action Type = Export to Shopify` and `Target Entity = Inventory Quantities`.
   - On-hand stock from each mapped Odoo location is calculated and pushed to the corresponding Shopify fulfillment location.
3. **Import Stock from Shopify by Location**:
   - In the **Sync Wizard**, select `Action Type = Import from Shopify` and `Target Entity = Inventory Quantities`.
   - The connector queries live inventory levels from each active Shopify location and automatically reconciles Odoo stock quantities using native inventory adjustments (`stock.quant`).
4. **Location-Aware Order Routing**:
   - When orders are downloaded from Shopify, the system inspects the fulfillment location assigned by Shopify.
   - If a matching Location Mapping exists, the Sales Order's fulfillment warehouse and delivery pickings are automatically routed to the designated warehouse.

---

### Declarative Metafields Mapping Engine

Synchronize custom data fields between Shopify and Odoo without writing custom code:

1. Navigate to **Shopify Connector** &rarr; **Mappings** &rarr; **Metafields** (or open the **Metafields** tab on the store form).
2. Click **New** to create a field mapping:
   - **Shopify Store**: Select your store instance.
   - **Applies To**: Choose the target model (`product.template`, `product.product`, `res.partner`, or `sale.order`).
   - **Odoo Field**: Select any standard or custom field from the dropdown.
   - **Shopify Namespace**: Enter the metafield namespace (default: `custom`).
   - **Shopify Key**: Enter the metafield key (e.g., `fabric_type`, `care_instructions`, `loyalty_tier`).
   - **Shopify Metafield Type**: Select the data type (`Single Line Text`, `Multi-Line Text`, `Integer`, `Decimal`, `Boolean`, `JSON`, `URL`).
   - **Sync Direction**: Choose `Bidirectional`, `Import Only`, or `Export Only`.
3. **During Sync**:
   - When importing products, variants, orders, or customers, mapped metafields are automatically extracted from Shopify and written into the designated Odoo fields.
   - When exporting products, mapped Odoo field values are formatted and uploaded as Shopify metafields.

---

### Automated Order Refund & Return Management

Manage Shopify refunds and customer returns directly inside Odoo:

1. **Automation Settings**:
   On your Shopify Store form under the **Automation & Workflows** tab:
   - **Auto-Process Refunds**: Ingest and process refunds automatically when orders are synced.
   - **Auto-Create Credit Notes**: Automatically generate customer Credit Notes (`account.move` of type `out_refund`) linked to the sales order.
   - **Auto-Post Credit Notes**: Automatically validate and post generated credit notes.
2. **Importing Refunds**:
   - **Automatic**: When orders are imported via webhook (`refunds_create`) or cron job, refund events are staged and processed automatically.
   - **Manual**: In the **Sync Wizard**, select `Action Type = Import from Shopify` and `Target Entity = Order Refunds`.
3. **Refund Tracking**:
   - View all refund records under **Shopify Connector** &rarr; **Mappings** &rarr; **Refunds**.
   - Each refund record tracks the Shopify Refund ID, original Sales Order, Customer, Refund Amount, Reason, and the generated Customer Credit Note.

---

### Manual Sync Wizard

The Sync Wizard allows on-demand bidirectional data synchronization with granular controls:

1. Navigate to **Shopify Connector** &rarr; **Operations** &rarr; **Sync Wizard** (or click **Sync Operations** directly on any store record).
2. Choose your parameters:
   - **Shopify Store**: Select the target store instance.
   - **Action Type**:
     - `Import from Shopify` (Fetch data from store into Odoo)
     - `Export to Shopify` (Push Odoo data to store)
   - **Target Entity**:
     - `Sales Orders` (Import)
     - `Products & Variants` (Import or Export)
     - `Customers` (Import)
     - `Inventory Quantities` (Import or Export by Location)
     - `Order Refunds` (Import)
   - **Max Records to Fetch**: Control batch size (default: 50, maximum: 250).
   - **Updated Since**: Optional datetime filter (fetches only items updated after this date).
   - **Immediately Process Feeds**: When checked, staging feeds are automatically converted into real Odoo records upon download.
3. Click **Execute Synchronization**.

---

### Staging Feeds (Lossless Queue)

To protect your live database against corrupted data, network interruptions, or mismatched configurations, incoming records enter the **Staging Feeds** queue (`shopify.feed`).

* View feeds under **Shopify Connector** &rarr; **Operations** &rarr; **Staging Feeds**.
* Feed States:
  - **Pending (`draft`)**: Downloaded and waiting for processing.
  - **Processed (`done`)**: Successfully converted into Odoo Customers, Products, or Orders.
  - **Failed (`error`)**: Encountered an issue during conversion (e.g., missing mandatory field or tax definition).
* **Fix & Retry**:
  If a feed fails, click on it to inspect the **Error Details** and the **Raw JSON Data**. After resolving the missing reference (e.g., creating a missing tax rate), click **Process Feed** to instantly retry.

---

### Bi-directional Mapping System

All synchronized data maintains an explicit cross-reference table under the **Mappings** menu:

1. **Products (`shopify.template.mapping`)**:
   - Maps Odoo `product.template` to Shopify Product IDs and URL Handles.
2. **Variants (`shopify.product.mapping`)**:
   - Maps specific `product.product` records to Shopify Variant IDs and Shopify Inventory Item IDs.
3. **Orders (`shopify.order.mapping`)**:
   - Maps Odoo `sale.order` to Shopify Order IDs, Order Numbers, Financial Status (`paid`, `pending`), and Fulfillment Status.
4. **Customers (`shopify.partner.mapping`)**:
   - Maps Odoo `res.partner` records to Shopify Customer IDs, emails, and phone numbers.
5. **Locations (`shopify.location.mapping`)**:
   - Maps Shopify fulfillment locations to Odoo Warehouses and stock locations.
6. **Metafields (`shopify.metafield.mapping`)**:
   - Maps Shopify custom metafields to Odoo model fields.
7. **Refunds (`shopify.refund.mapping`)**:
   - Maps Shopify refund events to Odoo customer credit notes and order records.
8. **Taxes (`shopify.tax.mapping`)**:
   - Maps Shopify tax titles (e.g., `State Tax`, `VAT`) to corresponding Odoo `account.tax` rates.

---

### Automated Real-time Delivery Fulfillment

When goods are shipped from your warehouse:

1. Open the delivery order under **Inventory** &rarr; **Delivery Orders** (`stock.picking`).
2. Enter the **Carrier Tracking Reference** and select the **Carrier**.
3. Click **Validate**.
4. The connector automatically detects the linked Shopify order:
   - Calls Shopify Fulfillment API.
   - Pushes the tracking number and carrier name.
   - Marks the order line items as fulfilled on Shopify.
   - Flags `shopify_fulfillment_synced = True` on the Odoo delivery picking.
   - Logs the transaction in Sync History.

---

### Scheduled Automation (Cron Jobs)

The connector includes pre-configured scheduled actions for background synchronization:

1. Enable **Developer Mode** and go to **Settings** &rarr; **Technical** &rarr; **Automation** &rarr; **Scheduled Actions**.
2. Active automated jobs:
   - **Shopify Connector: Auto-Sync Orders**:
     - Code: `model.cron_sync_orders()`
     - Default interval: Every 1 hour.
     - Automatically fetches new orders from all connected stores.
   - **Shopify Connector: Auto-Sync Inventory**:
     - Code: `model.cron_sync_inventory()`
     - Default interval: Every 30 minutes.
     - Automatically updates Shopify stock levels with current Odoo on-hand quantities across mapped locations.
3. Toggle the **Active** switch to enable or disable automated execution.

---

### Real-Time Webhooks Setup

For instant, event-driven updates without waiting for cron schedules:

1. **Webhook Endpoint URL**:
   ```text
   https://<your-odoo-domain>/shopify/webhook/<instance_id>/<topic>
   ```
   *Example*:
   ```text
   https://erp.example.com/shopify/webhook/1/orders_create
   ```

2. **Supported Topics**:
   - `orders_create`
   - `orders_updated`
   - `products_create`
   - `products_update`
   - `customers_create`
   - `refunds_create`

3. **Signature Verification (HMAC-SHA256)**:
   - Copy your Shopify Webhook Secret from Shopify Admin.
   - Paste it into the **Webhook Client Secret** field on your Shopify Store instance in Odoo.
   - All incoming webhooks verify the `X-Shopify-Hmac-Sha256` header before processing.

---

### Audit & Sync History Logs

Every operation (manual sync, webhook execution, cron run, fulfillment push) produces an audit entry under **Shopify Connector** &rarr; **Audit & Logs** &rarr; **Sync History**:

- **Operation Type**: Import, Export, Webhook.
- **Entity**: Store, Product, Order, Customer, Stock, Refund.
- **Status**: Success, Warning, Error.
- **Records Processed**: Count of records affected.
- **Detailed Message**: Contextual feedback or complete traceback on errors.

---

## Technical Architecture & Models

```text
odooteck_odoo_shopify_connector/
├── controllers/
│   └── shopify_webhook.py       # Public HTTP controller for HMAC verified webhooks
├── data/
│   ├── data.xml                 # Default sequences
│   └── cron.xml                 # Scheduled actions for orders & stock
├── models/
│   ├── shopify_client.py        # Dedicated Shopify API client wrapper
│   ├── shopify_instance.py      # Core store configuration & credentials
│   ├── shopify_feed.py          # Staging queue, order processing & metafield engine
│   ├── shopify_mappings.py      # Templates, variants, orders, partners, taxes, locations, metafields, refunds
│   ├── shopify_order.py         # Sale Order extensions & mapping logic
│   ├── shopify_partner.py       # Customer mapping helpers
│   ├── shopify_product.py       # Product & template extensions
│   ├── shopify_stock.py         # Delivery fulfillment sync override
│   └── shopify_sync_history.py  # Audit logging model
├── security/
│   ├── security.xml             # 3-tier security (category -> privilege -> groups)
│   └── ir.model.access.csv      # Access rights for users & managers
├── tests/
│   ├── __init__.py              # Test package initializer
│   └── test_shopify_connector.py# Complete unit test suite (8 comprehensive test cases)
├── views/
│   ├── menus.xml                # App navigation menus
│   ├── shopify_instance_views.xml
│   ├── shopify_feed_views.xml
│   ├── shopify_mapping_views.xml
│   ├── shopify_sync_history_views.xml
│   ├── shopify_sync_wizard_views.xml
│   └── inherited_views.xml      # Form extensions on sale.order, stock.picking, etc.
└── wizard/
    └── shopify_sync_wizard.py   # Interactive synchronization wizard
```

---

## Troubleshooting & FAQs

### Q: "Connection test failed: 401 Unauthorized"
* **Cause**: Invalid Admin API Access Token or incorrect Shopify store URL.
* **Solution**: Ensure your token starts with `shpat_` and has not been revoked. Verify the URL is in the format `https://<store-name>.myshopify.com`.

### Q: "Connection test failed: 403 Forbidden"
* **Cause**: Missing Admin API access scopes.
* **Solution**: Check app configuration in Shopify Admin and verify scopes (`read_orders`, `write_products`, `read_locations`, `read_inventory`, `write_inventory`, etc.) are granted.

### Q: How does Multi-Location stock sync work if I have multiple physical warehouses?
* **Solution**: In Odoo, open your Shopify Store and click **Discover Locations**. The connector automatically retrieves all Shopify fulfillment locations. Simply select the corresponding Odoo Warehouse and internal Stock Location for each row. The system will independently import and export quantities per location.

### Q: Can I map custom metafields from third-party Shopify apps into Odoo?
* **Solution**: Yes! Go to **Mappings** &rarr; **Metafields**, select the target model (e.g. `product.template`), specify the Shopify namespace and key, and select the corresponding Odoo field. The connector will automatically synchronize values during product and order feeds.

### Q: How are partial refunds handled?
* **Solution**: Partial refunds create a Customer Credit Note (`account.move`) in draft or posted state matching the exact refunded amount and line items received from Shopify, updating the order's financial status to `partially_refunded`.

---

## Copyright & Licensing

- **Author**: Odooteck
- **License**: Odoo Proprietary License v1.0 (OPL-1)
- **Copyright**: (c) Odooteck. All rights reserved.
