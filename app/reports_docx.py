# app/reports_docx.py
import io
import os
import datetime
from flask import Blueprint, request, send_file, abort, jsonify, render_template_string, current_app
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import mammoth
import os, io, datetime
import subprocess, tempfile, shutil, time, glob
from pathlib import Path
from .models import *


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

TEMPLATE_MAP = {
    "tracking": "menora_report.docx",   # your old tracking template
    "siudi":    "menora_siudi.docx",    # the new one
}

from datetime import datetime, date
from flask import request, current_app

# import your model
# from app.models import GilInsured   # <-- adjust to your actual import



def map_template_key(key: str) -> str:
    return TEMPLATE_MAP.get((key or "").lower(), TEMPLATE_MAP["tracking"])


def _deep_set(d: dict, dotted: str, value):
    """set nested dict value by dotted path (e.g., 'insured.name')."""
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value
    return d

def pick_template_for_report(report_id: int) -> str:
    # Phase-1: always use the Menora 'Siudi' template
    return "menora_siudi.docx"


# ---- context builder (KEEP THIS VERSION) ----
from datetime import datetime, date

def _fmt_d(d: date | None, fmt="%d/%m/%Y") -> str:
    return d.strftime(fmt) if d else ""

def _calc_age(birth: date | None, on: date | None = None) -> int | str:
    if not birth:
        return ""
    on = on or date.today()
    years = on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))
    return years

def _fetch_insured_row(insured_id: int) -> dict:
    ins = GilInsured.query.get(insured_id) if insured_id else None
    if not ins:
        return {}
    full_name = (" ".join(filter(None, [ins.last_name, ins.first_name]))).strip()
    db_fields = {
        "ref_number":   ins.ref_number or getattr(ins, "ref", "") or "",
        "full_name":    full_name,
        "birth_date":   _fmt_d(ins.birth_date),
        "gender":       ins.gender or "",
        "id_number":    ins.id_number or "",
        "claim_number": ins.claim_number or "",
        "age":          _calc_age(ins.birth_date),
    }
    return db_fields

def get_report_context(report_id: int, *, insured_id: int | None = None, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    db_fields  = _fetch_insured_row(insured_id) if insured_id else {}
    ctx_fields = {
        "activity_date": overrides.get("activity_date", ""),
        "surv_place":    overrides.get("surv_place", ""),
        "surv_city":     overrides.get("surv_city",  ""),
    }
    return {"db": db_fields, "ctx": ctx_fields, "now": datetime.now().strftime("%d/%m/%Y")}


def _collect_overrides_from_query(args) -> dict:
    """
    Read known inputs from request.args and build a nested overrides dict.
    Empty values are ignored (keep defaults).
    """
    mapping = {
        "activity_date": "case.activity_date",
        "claim_number": "case.claim_number",
        "insured_name": "insured.name",
        "insured_id": "insured.id",
        "insured_phone": "insured.phone",
        "injury_type": "insured.injury_type",
        "surv_place": "surveillance.place",
        "surv_city": "surveillance.city",
    }
    out = {}
    for qkey, path in mapping.items():
        val = (args.get(qkey) or "").strip()
        if val:
            _deep_set(out, path, val)
    return out

def _collect_overrides_from_json(json_body: dict | None) -> dict:
    """Same as query, but from a JSON body for the download route."""
    if not json_body:
        return {}
    fields = {
        "activity_date": "case.activity_date",
        "claim_number": "case.claim_number",
        "insured_name": "insured.name",
        "insured_id": "insured.id",
        "insured_phone": "insured.phone",
        "injury_type": "insured.injury_type",
        "surv_place": "surveillance.place",
        "surv_city": "surveillance.city",
    }
    out = {}
    for k, dotted in fields.items():
        val = (json_body.get(k) or "").strip()
        if val:
            _deep_set(out, dotted, val)
    return out


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

# --- add near other imports ---
import subprocess, tempfile, shutil
from flask import send_file

def _resolve_soffice_path() -> str:
    """
    Prefer soffice.exe on Windows; fall back to PATH.
    """
    from .config import Config
    cand = getattr(Config, "LIBREOFFICE_BIN", None)
    if cand and os.path.exists(cand):
        # normalize to .exe if someone pointed at soffice.com
        if cand.lower().endswith("soffice.com"):
            exe = cand[:-4] + "exe"
            if os.path.exists(exe):
                return exe
        return cand

    # Common Windows installs
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreOffice\program\soffice.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # PATH (may resolve to soffice.exe already)
    from shutil import which
    w = which("soffice")
    if w:
        # if it’s .com and .exe exists next to it, prefer .exe
        if w.lower().endswith("soffice.com"):
            exe = w[:-4] + "exe"
            if os.path.exists(exe):
                return exe
        return w

    return "soffice"


def _docx_to_pdf_bytes(docx_bytes: bytes) -> bytes:
    """
    Robust DOCX -> PDF on Windows/LibreOffice:
    - uses a temp user profile (avoids locks)
    - runs in the temp dir as CWD
    - tries 'pdf' then 'pdf:writer_pdf_Export'
    - scans for any *.pdf (LO sometimes renames)
    - waits for the file to actually appear
    """
    import subprocess, tempfile, shutil, time, glob
    from pathlib import Path

    soffice = _resolve_soffice_path()

    tmpdir = tempfile.mkdtemp(prefix="lo_")
    tmp = Path(tmpdir)
    try:
        docx_path = tmp / "report.docx"
        expected_pdf = tmp / "report.pdf"
        docx_path.write_bytes(docx_bytes)

        profile_url = tmp.as_uri() + "/lo_profile"

        def try_convert(filter_spec: str) -> tuple[int, str, str]:
            cmd = [
                soffice,
                "--headless", "--nologo", "--nodefault", "--nolockcheck",
                "--norestore", "--invisible",
                f"-env:UserInstallation={profile_url}",
                "--convert-to", filter_spec,
                "--outdir", str(tmp),
                str(docx_path),
            ]
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=str(tmp)
            )
            # wait up to 15s for *any* PDF to appear
            deadline = time.time() + 15.0
            while time.time() < deadline:
                if expected_pdf.exists():
                    break
                pdfs = list(tmp.glob("*.pdf"))
                if pdfs:
                    break
                time.sleep(0.2)
            return proc.returncode, proc.stdout, proc.stderr

        rc, out, err = try_convert("pdf")
        pdfs = sorted(tmp.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        if not pdfs:
            # second attempt with explicit filter
            rc2, out2, err2 = try_convert("pdf:writer_pdf_Export")
            out += "\n\n-- second attempt stdout --\n" + out2
            err += "\n\n-- second attempt stderr --\n" + err2
            pdfs = sorted(tmp.glob("*.pdf"), key=lambda p: p.stat().st_mtime)

        if not pdfs:
            listing = ""
            try:
                listing = "\n".join(p.name for p in tmp.iterdir())
            except Exception:
                listing = "(dir listing failed)"
            raise RuntimeError(
                "LibreOffice convert returned rc="
                f"{rc}, but no PDF found.\n"
                f"STDOUT:\n{out}\n\nSTDERR:\n{err}\n\n"
                f"TEMP DIR: {tmp}\nFILES:\n{listing}\n"
            )

        pdf_path = pdfs[-1]
        time.sleep(0.2)  # flush grace on Windows
        return pdf_path.read_bytes()

    finally:
        # try multiple times in case Windows locks the temp files briefly
        for _ in range(6):
            try:
                shutil.rmtree(tmpdir)
                break
            except Exception:
                time.sleep(0.3)


# ---- preview PDF (KEEP) ----
@reports_docx_bp.route("/<int:report_id>/preview-pdf", methods=["GET"])
def preview_docx_as_pdf(report_id: int):
    insured_id = request.args.get("insured_id", type=int)
    overrides = {
        "activity_date": request.args.get("activity_date", ""),
        "surv_place":    request.args.get("surv_place", ""),
        "surv_city":     request.args.get("surv_city",  ""),
    }
    context = get_report_context(report_id, insured_id=insured_id, overrides=overrides)
    tmpl_key = request.args.get("template", "tracking")
    template_path = load_template_docx(map_template_key(tmpl_key))
    docx_bytes = render_docx_bytes(template_path, context)
    pdf_bytes  = _docx_to_pdf_bytes(docx_bytes)
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")





@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def render_docx_endpoint(report_id: int):
    try:
        # still using hard-coded context for now
        context = get_report_context(report_id, overrides=None)

        data = request.get_json(silent=True) or {}
        tmpl_key = data.get("template") or request.args.get("template") or "tracking"
        template_path = load_template_docx(map_template_key(tmpl_key))
        current_app.logger.info(f"[DOCX] Using template: {template_path}")

        docx_bytes = render_docx_bytes(template_path, context)
        ensure_output_dir()
        fname = f"report_{report_id}.docx"
        disk_path = os.path.join(OUTPUT_DIR, fname)
        with open(disk_path, "wb") as f:
            f.write(docx_bytes)
        return jsonify({"ok": True, "docx_url": f"/reports/download/{fname}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---- download DOCX (KEEP) ----
@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def render_docx_download(report_id: int):
    data = request.get_json(silent=True) or {}
    insured_id = data.get("insured_id")
    overrides = {
        "activity_date": data.get("activity_date", ""),
        "surv_place":    data.get("surv_place", ""),
        "surv_city":     data.get("surv_city",  ""),
    }
    context = get_report_context(report_id, insured_id=insured_id, overrides=overrides)
    tmpl_key = data.get("template", "tracking")
    template_path = load_template_docx(map_template_key(tmpl_key))
    docx_bytes = render_docx_bytes(template_path, context)
    ensure_output_dir()
    version_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"report_{report_id}_{version_stamp}.docx"
    disk_path = os.path.join(OUTPUT_DIR, fname)
    with open(disk_path, "wb") as f:
        f.write(docx_bytes)
    return jsonify({"ok": True, "docx_url": f"/reports/{report_id}/download/{fname}"}), 200







