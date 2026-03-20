from decimal import Decimal
from . import db
from .models import GilInvoiceAR, GilPaymentNoticeLine, GilPaymentReconciliation


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


def recalculate_ar_invoice(ar_id: int):
    ar = GilInvoiceAR.query.get(ar_id)
    if not ar:
        raise ValueError(f"AR invoice {ar_id} not found")

    total_paid = (
        db.session.query(db.func.coalesce(db.func.sum(GilPaymentReconciliation.matched_amount), 0))
        .filter(GilPaymentReconciliation.ar_id == ar_id)
        .scalar()
    )

    total_paid = _d(total_paid)
    invoice_total = _d(ar.invoice_total)
    balance_due = invoice_total - total_paid

    if balance_due < Decimal("0.00"):
        balance_due = Decimal("0.00")

    ar.paid_total = total_paid
    ar.balance_due = balance_due
    ar.status = derive_ar_status(invoice_total, total_paid)

    return ar


def clear_line_reconciliation(line_id: int):
    line = GilPaymentNoticeLine.query.get(line_id)
    if not line:
        raise ValueError(f"Payment line {line_id} not found")

    old_ar_id = line.matched_ar_id

    GilPaymentReconciliation.query.filter_by(line_id=line_id).delete()
    line.matched_ar_id = None
    line.match_status = "Unmatched"

    if old_ar_id:
        recalculate_ar_invoice(old_ar_id)

    return line


def match_payment_line_to_ar(line_id: int, ar_id: int, user_id=None, note=None):
    line = GilPaymentNoticeLine.query.get(line_id)
    if not line:
        raise ValueError(f"Payment line {line_id} not found")

    ar = GilInvoiceAR.query.get(ar_id)
    if not ar:
        raise ValueError(f"AR invoice {ar_id} not found")

    match_amount = _d(line.net_amount)
    if match_amount <= Decimal("0.00"):
        raise ValueError("Line net amount must be greater than zero")

    old_ar_id = line.matched_ar_id

    # remove old reconciliation for this line first
    GilPaymentReconciliation.query.filter_by(line_id=line_id).delete()

    rec = GilPaymentReconciliation(
        ar_id=ar.ar_id,
        line_id=line.line_id,
        matched_amount=match_amount,
        match_type="Manual",
        note=note,
        matched_by=user_id
    )
    db.session.add(rec)

    line.matched_ar_id = ar.ar_id

    if match_amount < _d(ar.invoice_total):
        line.match_status = "Matched"
    else:
        line.match_status = "Matched"

    recalculate_ar_invoice(ar.ar_id)

    if old_ar_id and old_ar_id != ar.ar_id:
        recalculate_ar_invoice(old_ar_id)

    return {
        "line": line,
        "ar": ar,
        "reconciliation": rec,
        "matched_amount": match_amount
    }