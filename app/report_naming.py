import re
import unicodedata


def _clean_part(value):
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def sanitize_filename(filename: str) -> str:
    """
    Keep Hebrew/English/numbers/spaces/dash/underscore, remove unsafe filename chars.
    """
    filename = unicodedata.normalize("NFKC", filename or "").strip()
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename


def report_label_from_type(report_type: str) -> str:
    rt = (report_type or "").strip().lower()

    if rt in {"tracking", "siudi", "menora_life_followup"}:
        return "דוח מעקב"

    if rt in {"id_photos", "menora_life_photoid", "menora_life_photos"}:
        return "נספח זיהוי"

    if rt in {"siudi_invoice", "menora_life_invoice", "invoice"}:
        return "חשבון"

    return "דוח חקירה"


def build_report_display_name(
    report_type: str,
    full_name: str = "",
    reference_no: str = "",
    invoice_no: str = "",
    version_no: int | None = 0,
) -> str:
    """
    Human-readable report title / base filename without extension.
    version_no=0 -> no suffix
    version_no>0 -> append " - v<no>"
    """
    label = report_label_from_type(report_type)
    full_name = _clean_part(full_name)
    reference_no = _clean_part(reference_no)
    invoice_no = _clean_part(invoice_no)

    parts = [label]

    if full_name:
        parts.append(full_name)

    # Dor's request: invoices prefer invoice no; reports prefer reference no
    if label == "חשבון":
        if invoice_no:
            parts.append(invoice_no)
        elif reference_no:
            parts.append(reference_no)
    else:
        if reference_no:
            parts.append(reference_no)

    base = " - ".join(parts)

    try:
        v = int(version_no or 0)
    except Exception:
        v = 0

    if v > 0:
        base += f" - v{v}"

    return sanitize_filename(base)


def build_report_filename(
    report_type: str,
    full_name: str = "",
    reference_no: str = "",
    invoice_no: str = "",
    ext: str = "pdf",
    version_no: int | None = 0,
) -> str:
    base = build_report_display_name(
        report_type=report_type,
        full_name=full_name,
        reference_no=reference_no,
        invoice_no=invoice_no,
        version_no=version_no,
    )
    ext = (ext or "pdf").lstrip(".")
    return f"{base}.{ext}"

