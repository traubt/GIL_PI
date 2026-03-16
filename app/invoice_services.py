import json
from decimal import Decimal
from datetime import datetime, date

from . import db
from .models import GilInvoice, GilInvoiceItem


def _safe_decimal(value, default="0.00"):
    """
    Convert incoming value to Decimal safely.
    """
    try:
        if value in (None, "", "null"):
            return Decimal(default)
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal(default)


def _safe_date(value):
    """
    Accepts:
      - datetime.date
      - datetime.datetime
      - 'YYYY-MM-DD'
      - 'DD/MM/YYYY'
    Returns date or None.
    """
    if not value:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    value = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            continue

    return None


def _json_default_serializer(obj):
    """
    Helps json.dumps serialize date/datetime/Decimal.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

import json

from .models import GilInvoice


def load_invoice_draft(insured_id, source_type, source_id, template_type):
    """
    Load the current Draft invoice for a given invoice context.

    Match rule:
      insured_id + source_type + source_id + template_type + status='Draft'
    """
    try:
        invoice = (
            GilInvoice.query
            .filter_by(
                insured_id=int(insured_id),
                source_type=source_type,
                source_id=int(source_id),
                template_type=template_type,
                status='Draft'
            )
            .order_by(GilInvoice.updated_at.desc(), GilInvoice.invoice_id.desc())
            .first()
        )

        if not invoice:
            return {
                "success": True,
                "found": False,
                "message": "No invoice draft found."
            }

        payload = {}
        if invoice.render_payload_json:
            try:
                payload = json.loads(invoice.render_payload_json)
            except Exception:
                payload = {}

        return {
            "success": True,
            "found": True,
            "invoice_id": invoice.invoice_id,
            "version": invoice.version,
            "status": invoice.status,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "payload": payload
        }

    except Exception as e:
        return {
            "success": False,
            "found": False,
            "message": f"Failed to load invoice draft: {str(e)}"
        }


def save_invoice_draft(
    insured_id,
    source_type,
    source_id,
    template_type,
    invoice_data,
    line_items,
    user_id=None,
    tracking_report_id=None
):
    """
    Create or update a Draft invoice.

    Matching rule for existing draft:
      insured_id + source_type + source_id + template_type + status='Draft'

    Behavior:
      - if draft exists: update it and increment version
      - else: create new draft with version=1
      - replace line items
      - save render payload snapshot

    Parameters
    ----------
    insured_id : int
    source_type : str
    source_id : int
    template_type : str
    invoice_data : dict
        Header-level invoice data from the UI / render payload.
    line_items : list[dict]
        Structured invoice line items.
    user_id : int | None
    tracking_report_id : int | None

    Returns
    -------
    dict
        {
          "success": True,
          "invoice_id": ...,
          "version": ...,
          "is_new": True/False,
          "message": "..."
        }
    """
    try:
        existing = (
            GilInvoice.query
            .filter_by(
                insured_id=insured_id,
                source_type=source_type,
                source_id=source_id,
                template_type=template_type,
                status='Draft'
            )
            .order_by(GilInvoice.invoice_id.desc())
            .first()
        )

        is_new = existing is None

        if is_new:
            invoice = GilInvoice(
                insured_id=insured_id,
                source_type=source_type,
                source_id=source_id,
                tracking_report_id=tracking_report_id,
                template_type=template_type,
                status='Draft',
                version=1,
                created_by=user_id,
                updated_by=user_id
            )
            db.session.add(invoice)
            db.session.flush()  # get invoice_id
        else:
            invoice = existing
            invoice.version = (invoice.version or 0) + 1
            invoice.updated_by = user_id
            if tracking_report_id:
                invoice.tracking_report_id = tracking_report_id

        # -----------------------------
        # Update invoice header fields
        # -----------------------------
        invoice.invoice_number = invoice_data.get('invoice_number')
        invoice.inv_ref = invoice_data.get('inv_ref')
        invoice.inv_date = _safe_date(invoice_data.get('inv_date'))

        invoice.insurance_company = invoice_data.get('insurance_company')
        invoice.branch_name = invoice_data.get('branch_name')
        invoice.claim_number = invoice_data.get('claim_number')
        invoice.claim_subject = invoice_data.get('claim_subject')
        invoice.insured_name = invoice_data.get('insured_name')
        invoice.insured_id_number = invoice_data.get('insured_id_number')

        invoice.service_date = _safe_date(invoice_data.get('service_date'))
        invoice.service_date_from = _safe_date(invoice_data.get('service_date_from'))
        invoice.service_date_to = _safe_date(invoice_data.get('service_date_to'))

        invoice.subtotal = _safe_decimal(invoice_data.get('subtotal'))
        invoice.vat_percent = _safe_decimal(invoice_data.get('vat_percent', "18.00"), "18.00")
        invoice.vat_amount = _safe_decimal(invoice_data.get('vat_amount'))
        invoice.total_amount = _safe_decimal(invoice_data.get('total_amount'))
        invoice.currency_code = invoice_data.get('currency_code') or 'ILS'

        invoice.notes = invoice_data.get('notes')

        # Save exact snapshot used for rendering / rebuilding later
        payload_snapshot = {
            "invoice_data": invoice_data,
            "line_items": line_items,
            "meta": {
                "insured_id": insured_id,
                "source_type": source_type,
                "source_id": source_id,
                "template_type": template_type,
                "tracking_report_id": tracking_report_id
            }
        }
        invoice.render_payload_json = json.dumps(
            payload_snapshot,
            ensure_ascii=False,
            default=_json_default_serializer
        )

        # -----------------------------
        # Replace line items
        # -----------------------------
        GilInvoiceItem.query.filter_by(invoice_id=invoice.invoice_id).delete()

        for idx, row in enumerate(line_items or [], start=1):
            item = GilInvoiceItem(
                invoice_id=invoice.invoice_id,
                line_no=idx,
                service_date=_safe_date(row.get('service_date')),
                item_code=row.get('item_code'),
                description=(row.get('description') or '').strip() or f"Line {idx}",
                qty=_safe_decimal(row.get('qty', "1.00"), "1.00"),
                unit_price=_safe_decimal(row.get('unit_price')),
                amount=_safe_decimal(row.get('amount')),
                vat_ind=bool(row.get('vat_ind', True)),
                notes=row.get('notes')
            )
            db.session.add(item)

        db.session.commit()

        return {
            "success": True,
            "invoice_id": invoice.invoice_id,
            "version": invoice.version,
            "is_new": is_new,
            "message": "Draft invoice saved successfully."
        }

    except Exception as e:
        db.session.rollback()
        return {
            "success": False,
            "message": f"Failed to save draft invoice: {str(e)}"
        }