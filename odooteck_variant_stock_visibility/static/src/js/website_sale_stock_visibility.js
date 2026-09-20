(function () {
    "use strict";

    function getProductTemplateId(container) {
        const input = container.querySelector('input[name="product_template_id"]');
        return input ? input.value : null;
    }

    function getSelectedCombination(container) {
        const ids = [];
        container.querySelectorAll('input.js_variant_change:checked').forEach((el) => {
            ids.push(parseInt(el.value, 10));
        });
        container.querySelectorAll('select.js_variant_change').forEach((el) => {
            if (el.value) {
                ids.push(parseInt(el.value, 10));
            }
        });
        return ids.filter((id) => !isNaN(id));
    }

    async function callRoute(route, params) {
        let response;
        try {
            response = await fetch(route, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: params,
                    id: Date.now(),
                }),
            });
        } catch (e) {
            return null;
        }
        const data = await response.json();
        if (data.error) {
            return null;
        }
        return data.result;
    }

    function clearOutOfStock(container) {
        container.querySelectorAll('.o_out_of_stock').forEach((el) => {
            el.classList.remove('o_out_of_stock');
        });
        container.querySelectorAll('input.js_variant_change, select.js_variant_change option')
            .forEach((el) => { el.disabled = false; });
    }

    function applyOutOfStock(container, valueIds) {
        valueIds.forEach((id) => {
            const inputs = container.querySelectorAll(
                'input.js_variant_change[value="' + id + '"], select.js_variant_change option[value="' + id + '"]'
            );
            inputs.forEach((input) => {
                input.disabled = true;
                if (input.tagName === 'OPTION') {
                    // A <select> can only contain option/optgroup children: disabling
                    // the option is the only signal it can carry.
                    return;
                }
                const label = input.closest('label') || input.closest('.o_variant_pills') || input.parentElement;
                if (label) {
                    label.classList.add('o_out_of_stock');
                }
            });
        });
    }

    async function refreshOutOfStockOptions(container) {
        const templateId = getProductTemplateId(container);
        if (!templateId) {
            return;
        }
        const combinationIds = getSelectedCombination(container);
        const result = await callRoute('/website_sale/get_out_of_stock_values', {
            product_template_id: templateId,
            combination_ids: combinationIds,
        });
        clearOutOfStock(container);
        if (result && result.out_of_stock_value_ids) {
            applyOutOfStock(container, result.out_of_stock_value_ids);
        }
    }

    function getVariantContainer(el) {
        return el.closest('.js_main_product, form.js_add_cart_variants, #product_detail') || document;
    }

    function init() {
        document.querySelectorAll('.js_main_product, form.js_add_cart_variants').forEach((container) => {
            refreshOutOfStockOptions(container);
        });
    }

    document.addEventListener('change', (ev) => {
        if (ev.target.matches && ev.target.matches('.js_variant_change')) {
            refreshOutOfStockOptions(getVariantContainer(ev.target));
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
