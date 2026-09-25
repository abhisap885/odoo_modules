# Visual update

Replaced the hero banner and application icon. The root menu now references static/description/app_icon.png. Added a short, non-looping order-flow GIF plus static fallback, entry animation, and reduced-motion CSS to the existing documentation. Existing documentation sections and screenshots are retained.

## Apply
Replace the addon directory on your Odoo server, then upgrade odooteck_odoo_shopify_connector in database new123 and refresh the browser. The upgrade reloads the menu icon. Back up the database before upgrading.

Live installation was not verified: localhost:8019 was not reachable from the editing environment. HTML, referenced assets, manifest and XML were checked locally. App Store rendering was not verified; hosts may strip custom styles, so the GIF also works independently of CSS.

## Artwork
Generated with the built-in image-generation tool; Stitch was unavailable. No supplied API key or login details are included.
Hero prompt: Premium Odooteck Shopify × Odoo banner, midnight navy, emerald and plum, Connected commerce headline, linked shopping bag and ERP tile, products/orders/customers/inventory footer.
Icon prompt: Bold emerald shopping bag, mint and plum synchronization arrows, midnight rounded square, transparent exterior, legible at small sizes, no text.
