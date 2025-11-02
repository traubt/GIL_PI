# app/reports_docx.py
import io
import os
import datetime
from flask import Blueprint, request, send_file, abort, jsonify, render_template_string, current_app
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import mammoth

# ---- Use app config for paths ----
from .config import Config

DOCX_TEMPLATES_DIR = getattr(
    Config, "DOCX_TEMPLATES_DIR",
    os.environ.get("DOCX_TEMPLATES_DIR", "/mnt/data")
)
OUTPUT_DIR = getattr(
    Config, "DOCX_OUTPUT_DIR",
    os.environ.get("DOCX_OUTPUT_DIR", "/tmp/gil_reports")
)

reports_docx_bp = Blueprint("reports_docx", __name__, url_prefix="/reports")

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # helpful once at boot to confirm where files go
    try:
        current_app.logger.info(f"[DOCX] OUTPUT_DIR={OUTPUT_DIR}")
    except Exception:
        pass

def load_template_docx(template_name: str) -> str:
    """
    Returns absolute path to the DOCX template, using Config.DOCX_TEMPLATES_DIR.
    """
    path = os.path.join(DOCX_TEMPLATES_DIR, template_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template not found: {path}")
    # optional: log it for sanity
    try:
        current_app.logger.info(f"[DOCX] Using template: {path}")
    except Exception:
        pass
    return path

# app/reports_docx.py  (replace the whole function)
def get_report_context(report_id: int, overrides: dict | None = None) -> dict:
    auto_ref = f"{datetime.date.today():%Y%m%d}-{report_id:04d}"

    dob = "01/02/1977"  # sample for now
    # derive birth_year from dob; safe if you later make dob empty
    birth_year = ""
    try:
        # supports dd/mm/yyyy or yyyy-mm-dd
        if dob:
            parts = dob.replace("-", "/").split("/")
            if len(parts[2]) == 4:
                birth_year = parts[2]
            elif len(parts[0]) == 4:
                birth_year = parts[0]
    except Exception:
        birth_year = ""

    base = {
        "insurer": "מנורה חברה לביטוח",
        "case": {
            "series": "63878",
            "ref": auto_ref,
            "claim_number": "MN-2025-12345",
            "investigator": "דור גוזמן",
            "report_date": datetime.date.today().strftime("%d/%m/%Y"),
            "activity_date": "",
        },
        "insured": {
            "name": "סודרי רפאל",
            "id": "123456789",
            "phone": "050-1234567",
            "injury_type": "",
            "dob": dob,
            "birth_year": birth_year,
        },
        "surveillance": {
            "place": "מרכז קניות",
            "city": "תל אביב",
        },
        "intro": {"text": "לבקשתכם פעלנו לביצוע מעקב..."},
        "background": {"text": "פרטים נוספים בהתאם למידע שנאסף."},
        "occupation": {"text": "הנפגע עבד ____________."},
        "authority_checks": {"text": "לא אותרו אישורי ניכוי מס."},
        "dnb": {"text": "אין לנפגע מניות בחברות."},
        "osint": {"text": "לא אותר מידע רלבנטי."},
        "activity": [
            {"when": "09:12", "desc": "תחילת פעילות."},
            {"when": "15:37", "desc": "סיום במשרד."},
        ],
        "photos": {"landscape": [], "portrait": []},
        "footer_signature": "גיל סוכנות מידע וניהול",
    }

    if overrides and "activity_date" in overrides:
        base["case"]["activity_date"] = overrides["activity_date"] or ""

    return base


def render_docx_bytes(template_path: str, context: dict) -> bytes:
    """
    Renders a DOCX from template + context and returns it as bytes.
    Expects the DOCX to use real Jinja keys (e.g., {{ case.report_date }}).
    """
    tpl = DocxTemplate(template_path)
    tpl.render(context)
    buf = io.BytesIO()
    tpl.save(buf)
    return buf.getvalue()


# app/reports_docx.py  (updated routes)

@reports_docx_bp.route("/<int:report_id>/preview", methods=["GET"])
def preview_docx_as_html(report_id: int):
    """
    Generate-on-the-fly DOCX and convert to HTML for preview (Mammoth) with style mapping.
    Note: Word headers/footers are not rendered by Mammoth.
    """
    template_path = load_template_docx("menora_siudi.docx")

    # allow activity date injection for your test
    activity_date = request.args.get("activity_date", "").strip()
    context = get_report_context(report_id, overrides={"activity_date": activity_date} if activity_date else None)
    data = render_docx_bytes(template_path, context)

    # Map Word styles -> HTML classes we can style
    # Adjust names to your template’s styles if needed (Normal, Heading 1, Heading 2, Caption, Quote, Table Grid, etc.)
    style_map = """
    p[style-name='Normal'] => p.normal
    p[style-name='Heading 1'] => h1.h1
    p[style-name='Heading 2'] => h2.h2
    p[style-name='Heading 3'] => h3.h3
    p[style-name='Caption'] => p.caption
    r[style-name='Strong'] => b
    table => table.word
    table > tr => tr
    table > tr > td => td
    """

    result = mammoth.convert_to_html(io.BytesIO(data), style_map=style_map)
    html = result.value

    base = f"""<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="/static/css/word_preview.css">
  </head>
  <body>
    <div class="a4">
      <div class="page">
        {html}
      </div>
    </div>
  </body>
</html>"""
    return render_template_string(base)



@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def generate_docx(report_id: int):
    """
    Generate and persist a DOCX. Accepts JSON body with {"activity_date": "..."}.
    """
    ensure_output_dir()
    template_path = load_template_docx("menora_siudi.docx")

    activity_date = ""
    if request.is_json:
        body = request.get_json(silent=True) or {}
        activity_date = (body.get("activity_date") or "").strip()

    context = get_report_context(report_id, overrides={"activity_date": activity_date} if activity_date else None)

    try:
        data = render_docx_bytes(template_path, context)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    version_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{report_id}_{version_stamp}.docx"
    abs_path = os.path.join(OUTPUT_DIR, filename)
    with open(abs_path, "wb") as f:
        f.write(data)

    return jsonify({"ok": True, "docx_url": f"/reports/{report_id}/download/{filename}", "filename": filename})



@reports_docx_bp.route("/<int:report_id>/download/<path:filename>", methods=["GET"])
def download_docx(report_id: int, filename: str):
    """
    Download a previously generated DOCX.
    """
    abs_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(abs_path):
        abort(404)
    return send_file(abs_path, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")



