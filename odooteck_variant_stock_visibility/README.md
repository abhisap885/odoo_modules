# Product Variant Stock Visibility

## Overview
This Odoo 19 module prevents shoppers from selecting out-of-stock product variant options (size, color, ...) on eCommerce product pages. Options that would resolve to an out-of-stock variant are shown greyed out, struck through and badged "Out of Stock", and are disabled from selection.

## Features
- Automatically disables out-of-stock product variants on the eCommerce product page.
- Visually grays out unavailable options (size, color, etc.).
- Displays an "Out of Stock" badge on unavailable variants.
- Easy configuration via Website > Settings.

## Configuration
1. Go to **Website > Configuration > Settings**.
2. Find the product section and check the option to hide/disable out-of-stock variants.

## Usage
Simply browse to a product page that has variants. If a variant's stock falls to 0, it will automatically become unselectable on the frontend.
