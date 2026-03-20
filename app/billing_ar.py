from decimal import Decimal
from . import db
from .models import GilInvoice, GilInvoiceAR


def _d(val):
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val))


def derive_ar_status(invoice_total, paid_total):
    invoice_total = _d(invoice_total)
    paid_total = _d(paid_total)
    balance = invoice_total - paid_total

    if invoice_total <= Decimal("0.00"):
        return "Sent"

    if balance <= Decimal("0.00"):
        return "Paid"

    if paid_total > Decimal("0.00"):
        return "Partially Paid"

    return "Sent"


def sync_invoice_to_ar(invoice: GilInvoice, user_id=None):
    """
    Create or update gil_invoice_ar from gil_invoice.

    Rules:
    - one AR row per source invoice
    - paid_total is preserved from existing AR
    - balance_due and status are recalculated
    """
    if not invoice:
        raise ValueError("invoice is required")

    if not invoice.invoice_id:
        raise ValueError("invoice.invoice_id is required")

    if not invoice.invoice_number:
        raise ValueError("invoice.invoice_number is required before AR sync")

    ar = GilInvoiceAR.query.filter_by(source_invoice_id=invoice.invoice_id).first()

    if not ar:
        # fallback by invoice number in case old records were inserted before source_invoice_id was used
        ar = GilInvoiceAR.query.filter_by(invoice_no=invoice.invoice_number).first()

    if not ar:
        ar = GilInvoiceAR(
            source_invoice_id=invoice.invoice_id,
            created_by=user_id or invoice.finalized_by or invoice.updated_by or invoice.created_by
        )
        db.session.add(ar)

    paid_total = _d(ar.paid_total)
    invoice_total = _d(invoice.total_amount)

    ar.source_invoice_id = invoice.invoice_id
    ar.invoice_no = (invoice.invoice_number or "").strip()
    ar.invoice_date = invoice.inv_date
    ar.insured_id = invoice.insured_id

    # no insurance_company_id in GilInvoice yet, so leave AR insurance_company_id null for now
    ar.claim_no = invoice.claim_number
    ar.reference_no = invoice.inv_ref
    ar.service_type = invoice.template_type
    ar.description = invoice.claim_subject

    ar.amount_ex_vat = _d(invoice.subtotal)
    ar.vat_amount = _d(invoice.vat_amount)
    ar.invoice_total = invoice_total

    # preserve existing payments if any
    ar.paid_total = paid_total
    ar.balance_due = invoice_total - paid_total
    if ar.balance_due < Decimal("0.00"):
        ar.balance_due = Decimal("0.00")

    ar.status = derive_ar_status(invoice_total, paid_total)
    ar.pdf_path = invoice.latest_pdf_path
    ar.dropbox_path = invoice.dropbox_folder_path
    ar.notes = invoice.notes

    ar.updated_by = user_id or invoice.finalized_by or invoice.updated_by or invoice.created_by

    return ar