# invoice_template_config.py

INVOICE_TEMPLATE_CONFIG = {
    "SIUDI_INVOICE": {
        "template_type": "menora_siudi",
        "template_file": "invoice_monora_siudi.docx",

        "header_fields": {
            "invoice_number": "inv_number",
            "inv_date": "inv_date",
            "subtotal": "inv_subtotal",
            "vat_percent": "inv_vat_rate",
            "vat_amount": "inv_vat_amount",
            "total_amount": "inv_total",
        },

        "derived_fields": {
            "service_date": "ctx_activity_date",
        },

        "line_items_mode": "single",
        "single_line_item": {
            "description": "מעקב סיעודי",
            "amount_field": "inv_subtotal",
            "qty": 1,
            "item_code": "SIUDI"
        }
    },

    "MENORA_LIFE_INVOICE": {
        "template_type": "menora_life",
        "template_file": "invoice_menora_life.docx",

        "header_fields": {
            "invoice_number": "life_inv_number",
            "inv_date": "life_inv_date",
            "service_date": "life_followup_date",
            "subtotal": "life_subtotal",
            "vat_percent": "life_vat_percent",
            "vat_amount": "life_vat_amount",
            "total_amount": "life_total",
        },

        "line_items_mode": "multi",
        "multi_line_items": [
            {"description_field": "life_item1_final", "amount_field": "life_item1_total", "qty": 1, "item_code": "LIFE"},
            {"description_field": "life_item2_final", "amount_field": "life_item2_total", "qty": 1, "item_code": "LIFE"},
            {"description_field": "life_item3_final", "amount_field": "life_item3_total", "qty": 1, "item_code": "LIFE"},
            {"description_field": "life_item4_final", "amount_field": "life_item4_total", "qty": 1, "item_code": "LIFE"},
            {"description_field": "life_item5_final", "amount_field": "life_item5_total", "qty": 1, "item_code": "LIFE"},
        ]
    },
}