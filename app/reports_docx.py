# app/reports_docx.py
import io
import os
import datetime
from flask import Blueprint, request, send_file, abort, jsonify, render_template_string, current_app, url_for
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
     "siudi_invoice": "invoice_monora_siudi.docx",

    # === new Menora Life insurance templates ===
    "menora_life_followup": "menora_life_followup.docx",
    "menora_life_photos": "menora_life_photos.docx",  # placeholder until you build it
    "menora_life_photoid": "menora_photo_id.docx",  # reuse Siudi photo ID
    "menora_life_invoice": "menora_life_invoice.docx",  # placeholder until ready
}

from datetime import datetime, date
from flask import request, current_app

# import your model
# from app.models import GilInsured   # <-- adjust to your actual import





def ddmmyyyy(iso_str: str) -> str:
    try:
        return datetime.strptime(iso_str.strip(), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return iso_str or ""

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

def _parse_tracking_rows(raw: str):
    """
    Parse lines like '06:00 - הגיע לכתובת...' into
    [{'time': '06:00', 'text': 'הגיע לכתובת...'}, ...]
    """
    rows = []
    if not raw:
        return rows

    for line in raw.splitlines():
        line = (line or "").strip()
        if not line:
            continue

        time_part = ""
        text_part = ""

        # Accept 'HH:MM - text' or 'HH:MM text'
        # First try a dash close to the start
        dash_idx = line.find("-")
        if 0 <= dash_idx <= 6:
            time_part = line[:dash_idx].strip()
            text_part = line[dash_idx + 1 :].strip()
        else:
            parts = line.split(None, 1)
            if len(parts) == 2:
                time_part, text_part = parts[0].strip(), parts[1].strip()
            else:
                # no clear time, treat entire line as text
                text_part = line

        rows.append({"time": time_part, "text": text_part})

    return rows

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

def _iso_to_dots(iso: str | None) -> str:
    """
    'YYYY-MM-DD' -> 'D.MM.YYYY'  (no leading zero on day; month stays 2-digit)
    """
    if not iso or len(iso) < 10:
        return ""
    y, m, d = iso[:10].split("-")
    # remove leading zero from day
    d = str(int(d))
    return f"{d}.{m}.{y}"

from datetime import datetime

def _now_hebrew() -> str:
    """Return date like: '2025 בנובמבר 4' (Hebrew month with ב- prefix, no leading zero)."""
    months = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני",
              "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]
    dt = datetime.now()
    month_he = f"ב{months[dt.month - 1]}"
    return f"{dt.day} {month_he} {dt.year}"


import re

def _to_iso(date_str: str | None) -> str:
    """
    Accept 'YYYY-MM-DD' or 'DD/MM/YYYY' (also D/M/YYYY) and return ISO 'YYYY-MM-DD'.
    Returns '' if parsing fails.
    """
    if not date_str:
        return ""
    s = date_str.strip()
    # Already ISO?
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # DD/MM/YYYY or D/M/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{int(mth):02d}-{int(d):02d}"
    return ""  # unknown format

def _iso_to_dots(iso: str | None) -> str:
    """
    Accept ISO 'YYYY-MM-DD' (or DD/MM/YYYY defensively) and return 'D.MM.YYYY'.
    """
    if not iso:
        return ""
    # normalize if got DD/MM/YYYY by mistake
    if "/" in iso:
        iso = _to_iso(iso)
    if not iso or len(iso) < 10 or "-" not in iso:
        return ""
    y, m, d = iso[:10].split("-")
    d = str(int(d))             # no leading zero for day
    return f"{d}.{m}.{y}"

# put near other helpers
def _gender_lex(gender_raw: str | None) -> dict:
    """
    Returns Hebrew words that change by gender.
    Accepts values like 'זכר'/'נקבה' or 'male'/'female'/'M'/'F'.
    """
    g = (gender_raw or "").strip().lower()
    is_female = g in {"נקבה", "female", "f", "נשים", "אשה", "אישה"}
    return {
        "is_female": is_female,
        "insured_label": "מבוטחת" if is_female else "מבוטח",
        "born_word":     "ילידת"   if is_female else "יליד",
        "claims_verb":   "טוענת"   if is_female else "טוען",
        "obj_suffix":    "ה"        if is_female else "ו",  # לתעדה / לתעדו
        "house_poss":    "ה"        if is_female else "ו",  # ביתה / ביתו
        "state_poss":    "ה"        if is_female else "ו",  # מצבה / מצבו
        "func_poss":     "ה"        if is_female else "ו",  # תפקודה / תפקודו
        "photos_poss":   "תמונותיה" if is_female else "תמונותיו",
        "pronoun_subj":  "היא"      if is_female else "הוא",
        "pronoun_obj":   "אותה"     if is_female else "אותו",
    }



def _fetch_insured_row(insured_id: int) -> dict:
    ins = GilInsured.query.get(insured_id) if insured_id else None
    if not ins:
        return {}
    full_name = (" ".join(filter(None, [ins.last_name, ins.first_name]))).strip()
    birth_year = ins.birth_date.year if getattr(ins, "birth_date", None) else ""
    return {
        "ref_number":   ins.ref_number or getattr(ins, "ref", "") or "",
        "full_name":    full_name,
        "birth_date":   _fmt_d(ins.birth_date),       # keep if some templates still use it
        "birth_year":   str(birth_year),
        "gender":       ins.gender or "",
        "id_number":    ins.id_number or "",
        "claim_number": ins.claim_number or "",
        "phone": ins.phone or "",
        "age":          _calc_age(ins.birth_date),
        "injury_type":  getattr(ins, "injury_type", "") or "",
    }

def get_report_context(report_id: int, *, insured_id: int | None = None, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    db_fields  = _fetch_insured_row(insured_id) if insured_id else {}

    # activity date (same as before)
    raw_date   = overrides.get("activity_date", "")
    act_iso    = _to_iso(raw_date) or raw_date

    ctx_fields = {
        "activity_date": act_iso,
        "activity_date_dots": _iso_to_dots(act_iso),
        "surv_place": overrides.get("surv_place", ""),
        "surv_city": overrides.get("surv_city", ""),
        "injury_type": overrides.get("injury_type", ""),
    }

    # === Menora Life Follow-up additional context ===
    ctx_fields.update({
        "injury_type": overrides.get("injury_type", ""),
    })

    # ---- pull Menora Life fields from overrides ----
    bg              = overrides.get("background", "")
    occupation      = overrides.get("occupation", "")
    social_media    = overrides.get("social_media", "")
    social_ident    = overrides.get("social_media_identification", "")
    tracking_date   = overrides.get("tracking_date", "")
    start_time      = overrides.get("start_time", "")
    end_time        = overrides.get("end_time", "")
    summary         = overrides.get("summary", "")
    authorities_1   = overrides.get("authorities_1", "")
    dnb             = overrides.get("dnb", "")          # 👈 NEW
    authorities_2   = overrides.get("authorities_2", "")

    db_fields.update({
        "background": bg,
        "occupation": occupation,
        "social_media": social_media,
        "social_media_identification": social_ident,
        "tracking_date": tracking_date,
        "start_time": start_time,
        "end_time": end_time,
        "summary": summary,
        "authorities_1": authorities_1,
        "dnb": dnb,
        "authorities_2": authorities_2,
    })

    phone_override = overrides.get("phone", "")
    if phone_override:
        db_fields["phone"] = phone_override

    # 🔹 DEBUG: what’s going into db.background?
    try:
        current_app.logger.info(
            "[CTX] get_report_context: db.background=%r (report_id=%s, insured_id=%s)",
            db_fields.get("background", ""),
            report_id,
            insured_id,
        )
    except Exception:
        pass

    lex = _gender_lex(db_fields.get("gender"))

    return {
        "db": db_fields,
        "ctx": ctx_fields,
        "lex": lex,
        "now": _now_hebrew(),
    }





def _collect_overrides_from_query(args) -> dict:
    """
    Read known inputs from request.args and build a nested overrides dict.
    Empty values are ignored (keep defaults).
    """
    mapping = {
        # ---- generic fields (existing) ----
        "activity_date": "case.activity_date",
        "claim_number": "case.claim_number",
        "insured_name": "insured.name",
        "insured_id": "insured.id",
        "insured_phone": "insured.phone",
        "injury_type": "insured.injury_type",
        "surv_place": "surveillance.place",
        "surv_city": "surveillance.city",

        # ---- Menora Life follow-up fields ----
        "background": "db.background",
        "occupation": "insured.occupation",
        "social_media": "insured.social_media",
        "social_media_identification": "insured.social_media_identification",
        "tracking_date": "case.tracking_date",
        "start_time": "case.start_time",
        "end_time": "case.end_time",
        "summary": "case.summary",
        "authorities_1": "case.authorities_1",
        "authorities_2": "case.authorities_2",
        "dnb": "db.dnb",
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

        # --- Menora Life Follow-up extra fields ---
        "background": "db.background",
        "occupation": "insured.occupation",
        "social_media": "insured.social_media",
        "social_media_identification": "insured.social_media_identification",
        "tracking_date": "case.tracking_date",
        "start_time": "case.start_time",
        "end_time": "case.end_time",
        "summary": "case.summary",
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


# ---- preview PDF (REPLACE with photo-aware) ----
# ====== imports this block relies on (ensure these exist at top of file) ======
# import os, io, tempfile
# from flask import request, send_file, current_app
# from docxtpl import DocxTemplate, InlineImage
# from docx.shared import Mm
# from PIL import Image, ImageOps   # if Pillow not installed, pip install pillow

# ====== small helpers (drop in once) =========================================
# ---- helpers: tmpdir, orientation, resize, preprocess (with logging) ----
from contextlib import contextmanager
from PIL import Image, ImageOps  # make sure Pillow is installed

@contextmanager
def _tmpdir(prefix="report_img_"):
    td = tempfile.TemporaryDirectory(prefix=prefix)
    try:
        yield td.name
    finally:
        td.cleanup()

def _detect_orientation(path: str) -> str:
    """Return 'portrait' if height >= width*1.10 after EXIF rotate, else 'landscape'."""
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            return "portrait" if (h / max(1, w)) >= 1.10 else "landscape"
    except Exception:
        return "landscape"

def _resize_copy(src: str, dst: str, max_w: int, max_h: int, quality: int = 82) -> tuple[int,int,int,int]:
    """
    Resize into dst (JPEG) with EXIF rotation, keep aspect.
    Returns (orig_w, orig_h, new_w, new_h).
    """
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        ow, oh = im.size
        im.thumbnail((max_w, max_h), Image.LANCZOS)
        nw, nh = im.size
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(dst, format="JPEG",
                quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
        return ow, oh, nw, nh

def _preprocess_for_docx(tmpdir: str, paths: list[str]) -> list[dict]:
    """
    For each path, produce a dict:
      { "path": <processed_path>, "guess": "portrait"/"landscape",
        "ow": <orig_w>, "oh": <orig_h>, "w": <new_w>, "h": <new_h> }
    """
    out: list[dict] = []
    for idx, p in enumerate(paths):
        guess = _detect_orientation(p)
        # caps: keep files small but clear
        max_w, max_h = ((700, 1100) if guess == "portrait" else (1400, 900))
        dst = os.path.join(tmpdir, f"img_{idx:03d}.jpg")
        try:
            ow, oh, nw, nh = _resize_copy(p, dst, max_w, max_h, quality=80)
            current_app.logger.info(
                "[PREPROC] %s -> %s | guess=%s | orig=%dx%d -> proc=%dx%d",
                os.path.basename(p), os.path.basename(dst), guess, ow, oh, nw, nh
            )
            out.append({"path": dst, "guess": guess, "ow": ow, "oh": oh, "w": nw, "h": nh})
        except Exception as e:
            current_app.logger.warning("[PREPROC] failed %s: %s; using original", p, e)
            # fall back to original (we don’t know processed size, so re-open to get it)
            try:
                with Image.open(p) as im:
                    im = ImageOps.exif_transpose(im)
                    nw, nh = im.size
            except Exception:
                nw = nh = 0
            out.append({"path": p, "guess": guess, "ow": 0, "oh": 0, "w": nw, "h": nh})
    return out



def _report_media_root() -> str:
    return current_app.config.get(
        "REPORT_MEDIA_DIR",
        os.path.join(current_app.instance_path, "report_media")
    )

# ====== FULL ROUTE: /reports/<id>/preview-pdf  ===============================
# ==== Preview to PDF (photo-aware, fixed sizes, 2-up portrait) ====
# ---- preview PDF: two-portraits-per-row without tables ----
@reports_docx_bp.route("/<int:report_id>/preview-pdf", methods=["GET"])
def preview_docx_as_pdf(report_id: int):
    import io, os
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm

    insured_id = request.args.get("insured_id", type=int)

    # ---- collect overrides from the query (including background) ----
    overrides = {
        "activity_date": (request.args.get("activity_date") or "").strip(),
        "surv_place":    (request.args.get("surv_place") or "").strip(),
        "surv_city":     (request.args.get("surv_city")  or "").strip(),
        "injury_type":   (request.args.get("injury_type") or "").strip(),

        # Menora Life follow-up fields (we care about background here)
        "background":    (request.args.get("background") or "").strip(),
        "occupation":    (request.args.get("occupation") or "").strip(),
        "social_media":  (request.args.get("social_media") or "").strip(),
        "social_media_identification":
            (request.args.get("social_media_identification") or "").strip(),
        "tracking_date": (request.args.get("tracking_date") or "").strip(),
        "start_time":    (request.args.get("start_time") or "").strip(),
        "end_time":      (request.args.get("end_time") or "").strip(),
        "summary":       (request.args.get("summary") or "").strip(),
        "authorities_1": (request.args.get("authorities_1") or "").strip(),
        "authorities_2": (request.args.get("authorities_2") or "").strip(),
        "phone": (request.args.get("phone") or "").strip(),
        "dnb": (request.args.get("dnb") or "").strip(),
    }

    # 🔹 DEBUG: raw value arriving from the client
    try:
        current_app.logger.info(
            "[CTX][preview] query.background=%r (report_id=%s, insured_id=%s)",
            overrides["background"],
            report_id,
            insured_id,
        )
    except Exception:
        pass

    ctx = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

    # --- template path ---
    tmpl_key = (request.args.get("template", "siudi") or "siudi").strip().lower()
    template_path = load_template_docx(map_template_key(tmpl_key))  # full path
    current_app.logger.info("[DOCX] Using template: %s", template_path)

    tpl = DocxTemplate(template_path)

    # --- Menora life follow-up: tracking activities table ---
    if tmpl_key == "menora_life_followup":
        raw = (request.args.get("tracking_raw") or "").strip()
        if raw:
            ctx["tracking_rows"] = _parse_tracking_rows(raw)
        else:
            ctx["tracking_rows"] = []


    # ===================== SIUDI INVOICE (no photos) ======================
    if tmpl_key == "siudi_invoice":
        g = request.args.get
        inv_date_iso = (g("inv_date") or "").strip()
        # ensure nested dicts exist
        ctx.setdefault("insured", {})
        ctx.setdefault("claim", {})
        ctx.setdefault("totals", {})

        ctx.update({
            "inv_date":    ddmmyyyy(inv_date_iso),
            "inv_number":  (g("inv_number") or "").strip(),
            "inv_ref":     (g("inv_ref") or "").strip(),
        })
        ctx["insured"]["id_number"] = (g("insured.id_number") or "").strip()
        ctx["claim"]["number"]      = (g("claim.number") or "").strip()
        ctx["claim"]["subject"]     = (g("claim.subject") or "").strip()
        ctx["totals"].update({
            "subtotal":   (g("totals_subtotal") or "").strip(),
            "vat_rate":   (g("totals_vat_rate") or "").strip(),
            "vat_amount": (g("totals_vat_amount") or "").strip(),
            "total":      (g("totals_total") or "").strip(),
        })

        # render -> pdf
        buf = io.BytesIO()
        tpl.render(ctx)
        tpl.save(buf)
        pdf_bytes = _docx_to_pdf_bytes(buf.getvalue())
        return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")
    # =====================================================================

    # --- collect selected files (names) -> absolute paths ---
    selected = request.args.getlist("selected_photos[]") or request.args.getlist("selected_photos")
    selected = [os.path.basename(n) for n in selected if n]
    case_id   = (request.args.get("insured_id") or request.args.get("case_id") or "").strip()
    rep_id    = str(report_id)
    media_root = current_app.config.get("REPORT_MEDIA_DIR", os.path.join(current_app.instance_path, "report_media"))

    def resolve_one(name: str) -> str | None:
        p = os.path.join(media_root, case_id, rep_id, name)
        if os.path.isfile(p): return p
        root_case = os.path.join(media_root, case_id)
        for root, _d, files in os.walk(root_case):
            if name in files:
                return os.path.join(root, name)
        current_app.logger.warning("[PHOTOS] not found: %s", name)
        return None

    paths = [p for n in selected if (p := resolve_one(n))]
    if not paths:
        folder = os.path.join(media_root, case_id, rep_id)
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                    paths.append(os.path.join(folder, fn))

    # --- classify by orientation ---
    from PIL import Image
    lands, ports = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                w, h = im.size
            (lands if w >= h else ports).append(p)
        except Exception as e:
            current_app.logger.warning("[PHOTOS] failed to open %s: %s", p, e)

    LAND_W = Mm(120)
    PORT_W = Mm(76)

    land_images = [InlineImage(tpl, p, width=LAND_W) for p in lands]

    def chunk2(items):
        it = iter(items)
        for a in it:
            b = next(it, None)
            yield a, b

    port_rows = []
    for l, r in chunk2(ports):
        left  = InlineImage(tpl, l, width=PORT_W)
        right = InlineImage(tpl, r, width=PORT_W) if r else None
        port_rows.append((left, right))

    gap = "\u00A0" * 8

    ctx.update({
        "land_images": land_images,
        "port_rows":   port_rows,
        "gap":         gap,
    })

    buf = io.BytesIO()
    tpl.render(ctx)
    tpl.save(buf)
    docx_bytes = buf.getvalue()

    pdf_bytes = _docx_to_pdf_bytes(docx_bytes)
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")



@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def render_docx_download(report_id: int):
    import io, os, datetime, json
    from PIL import Image
    from flask import current_app, request, jsonify, url_for
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm

    payload = request.get_json(silent=True) or {}

    insured_id = payload.get("insured_id")

    # ---- collect overrides from JSON (including background) ----
    overrides = {
        "activity_date": payload.get("activity_date", "").strip(),
        "surv_place":    payload.get("surv_place", "").strip(),
        "surv_city":     payload.get("surv_city",  "").strip(),
        "injury_type":   payload.get("injury_type", "").strip(),

        # Menora Life follow-up fields
        "background":    payload.get("background", "").strip(),
        "occupation":    payload.get("occupation", "").strip(),
        "social_media":  payload.get("social_media", "").strip(),
        "social_media_identification":
            payload.get("social_media_identification", "").strip(),
        "tracking_date": payload.get("tracking_date", "").strip(),
        "start_time":    payload.get("start_time", "").strip(),
        "end_time":      payload.get("end_time", "").strip(),
        "summary":       payload.get("summary", "").strip(),
        "authorities_1": payload.get("authorities_1", "").strip(),
        "authorities_2": payload.get("authorities_2", "").strip(),
        "phone": payload.get("phone", "").strip(),
        "dnb": payload.get("dnb", "").strip(),
    }

    # 🔹 DEBUG: raw value from download POST
    try:
        current_app.logger.info(
            "[CTX][download] payload.background=%r (report_id=%s, insured_id=%s)",
            overrides["background"],
            report_id,
            insured_id,
        )
    except Exception:
        pass

    ctx = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

    # --- template path ---
    tmpl_key = (payload.get("template") or "siudi").strip().lower()
    template_path = load_template_docx(map_template_key(tmpl_key))
    current_app.logger.info("[DOCX] Using template: %s", template_path)

    tpl = DocxTemplate(template_path)

    if tmpl_key == "menora_life_followup":
        raw = (payload.get("tracking_raw") or "").strip()
        if raw:
            ctx["tracking_rows"] = _parse_tracking_rows(raw)
        else:
            ctx.setdefault("tracking_rows", [])

    # ===================== SIUDI INVOICE (no photos) ======================
    if tmpl_key == "siudi_invoice":
        inv_date_iso = (payload.get("inv_date") or "").strip()
        # ensure nested dicts exist
        ctx.setdefault("insured", {})
        ctx.setdefault("claim", {})
        ctx.setdefault("totals", {})

        # values typed in the invoice card
        ctx.update({
            "inv_date":    ddmmyyyy(inv_date_iso),
            "inv_number":  (payload.get("inv_number") or "").strip(),
            "inv_ref":     (payload.get("inv_ref") or "").strip(),
        })
        # pulled from state/client
        ctx["insured"]["id_number"] = (payload.get("insured", {}).get("id_number") or "").strip()
        ctx["claim"]["number"]      = (payload.get("claim",   {}).get("number")    or "").strip()
        ctx["claim"]["subject"]     = (payload.get("claim",   {}).get("subject")   or "").strip()
        ctx["totals"].update({
            "subtotal":   (payload.get("totals", {}).get("subtotal")   or "").strip(),
            "vat_rate":   (payload.get("totals", {}).get("vat_rate")   or "").strip(),
            "vat_amount": (payload.get("totals", {}).get("vat_amount") or "").strip(),
            "total":      (payload.get("totals", {}).get("total")      or "").strip(),
        })

        # --- render and save to instance/generated_reports ---
        out_dir = os.path.join(current_app.instance_path, "generated_reports")
        os.makedirs(out_dir, exist_ok=True)

        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{report_id}_{stamp}.docx"
        abs_path = os.path.join(out_dir, filename)

        tpl.render(ctx)
        tpl.save(abs_path)

        docx_url = url_for("generated_reports", filename=filename)
        return jsonify({"ok": True, "docx_url": docx_url})
    # =====================================================================

    # --- collect selected names from payload ---
    names = payload.get("selected_photos") or []
    if not names and isinstance(payload.get("photos"), list):
        names = [os.path.basename(p.get("name", "")) for p in payload["photos"] if p.get("name")]
    names = [os.path.basename(n) for n in names if n]

    # --- resolve to absolute paths ---
    case_id    = str(insured_id or payload.get("case_id", "")).strip()
    rep_id     = str(report_id)
    media_root = current_app.config.get(
        "REPORT_MEDIA_DIR",
        os.path.join(current_app.instance_path, "report_media")
    )

    def resolve_one(name: str) -> str | None:
        exact = os.path.join(media_root, case_id, rep_id, name)
        if os.path.isfile(exact): return exact
        case_root = os.path.join(media_root, case_id)
        if os.path.isdir(case_root):
            for root, _dirs, files in os.walk(case_root):
                if name in files:
                    return os.path.join(root, name)
        current_app.logger.warning("[PHOTOS] not found: %s", name)
        return None

    paths = [p for n in names if (p := resolve_one(n))]

    # fallback: include all images in the report folder if none selected
    if not paths:
        folder = os.path.join(media_root, case_id, rep_id)
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                    paths.append(os.path.join(folder, fn))

    # --- orientation split using real pixel sizes ---
    lands, ports = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                w, h = im.size
            (lands if w >= h else ports).append(p)
        except Exception as e:
            current_app.logger.warning("[PHOTOS] open fail %s: %s", p, e)

    # --- sizes (match preview) ---
    LAND_W = Mm(120)
    PORT_W = Mm(76)

    land_images = [InlineImage(tpl, p, width=LAND_W) for p in lands]

    def chunk2(items):
        it = iter(items)
        for a in it:
            b = next(it, None)
            yield a, b

    port_rows = []
    for l, r in chunk2(ports):
        left  = InlineImage(tpl, l, width=PORT_W)
        right = InlineImage(tpl, r, width=PORT_W) if r else None
        port_rows.append((left, right))

    gap = "\u00A0" * 8

    ctx.update({
        "land_images": land_images,
        "port_rows":   port_rows,
        "gap":         gap,
    })

    # --- render and save to instance/generated_reports ---
    out_dir = os.path.join(current_app.instance_path, "generated_reports")
    os.makedirs(out_dir, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{report_id}_{stamp}.docx"
    abs_path = os.path.join(out_dir, filename)

    tpl.render(ctx)
    tpl.save(abs_path)

    docx_url = url_for("generated_reports", filename=filename)
    return jsonify({"ok": True, "docx_url": docx_url})



# ===================== PHOTO ID: dedicated endpoints (server only) =====================

import datetime as dt


# --------------------------- PHOTO-ID: Preview (PDF) ---------------------------

def _resolve_photo_id_image(insured_id, report_id, name_or_path):
    """
    Try to resolve the image for the photo-id report.

    - If we get an absolute filesystem path (local Dropbox on the server) – use it.
    - Otherwise, treat it as a file name and look for it under REPORT_MEDIA_DIR
      for this insured (in any subfolder), with a preference to the report folder.
    """
    if not name_or_path:
        return None

    s = str(name_or_path).strip()
    if not s:
        return None

    # If someone accidentally passed a data: URL, we can't handle it here
    if s.startswith("data:"):
        current_app.logger.warning(
            "[PhotoID] got data: URL for insured=%s report=%s; cannot resolve on server",
            insured_id, report_id
        )
        return None

    media_root = current_app.config.get(
        "REPORT_MEDIA_DIR",
        os.path.join(current_app.instance_path, "report_media")
    )

    # 1) Direct filesystem path (Dropbox local path on the server)
    if (s.startswith("/") or ":" in s) and os.path.isfile(s):
        return s

    # 2) If it's a URL, strip querystring/fragment and use the basename
    if "?" in s or "#" in s:
        s = s.split("?", 1)[0].split("#", 1)[0]
    base = os.path.basename(s)

    # Prefer: <media_root>/<insured_id>/<report_id>/<base>
    cand = os.path.join(media_root, str(insured_id), str(report_id), base)
    if os.path.isfile(cand):
        return cand

    # Fallback: search anywhere under this insured's folder
    insured_root = os.path.join(media_root, str(insured_id))
    if os.path.isdir(insured_root):
        for root, _dirs, files in os.walk(insured_root):
            if base in files:
                return os.path.join(root, base)

    current_app.logger.warning(
        "[PhotoID] cannot resolve image %r for insured=%s report=%s",
        name_or_path, insured_id, report_id
    )
    return None


@reports_docx_bp.get("/<int:report_id>/photo-id/preview-pdf")
def photo_id_preview_pdf(report_id: int):
    insured_id = request.args.get("insured_id", type=int) or 0

    id_date  = request.args.get("id_photo_date_text", "") or request.args.get("id_photo_date", "")
    id_time  = request.args.get("id_photo_time", "")
    id_city  = (request.args.get("id_photo_city") or "").strip()
    id_place = (request.args.get("id_photo_place") or "").strip()

    # Source selected in the "תמונת זיהוי" widget (now usually a short name)
    id_src = (request.args.get("id_photo_src") or "").strip()

    # Also look at selected_photos[] (we always send one basename from the client)
    names = request.args.getlist("selected_photos[]") or request.args.getlist("selected_photos") or []
    base_name = names[0] if names else None

    # If we somehow got the route name 'serve' as a "filename", ignore it
    if base_name and base_name.lower() == "serve":
        base_name = None

    # Prefer the explicit server-side filename; fall back to id_src only if needed
    key = base_name or id_src
    img_path = _resolve_photo_id_image(insured_id, report_id, key)


    current_app.logger.info(
        "[PhotoID][preview] report=%s insured=%s src=%r base=%r -> %r",
        report_id, insured_id, id_src, base_name, img_path
    )

    # build context
    ctx = get_report_context(report_id, insured_id=insured_id)
    place_str = ", ".join(v for v in (id_place, id_city) if v)
    ctx.update({
        "id_date":  id_date or _iso_to_dots(ctx.get("ctx", {}).get("activity_date", "")),
        "id_time":  id_time,
        "id_place": place_str,
    })

    template_path = os.path.join(current_app.root_path, "docx_templates", "menora_photo_id.docx")
    current_app.logger.info("[PhotoID][preview] template: %s", template_path)

    tpl = DocxTemplate(template_path)
    if img_path:
        ctx["id_photo"] = InlineImage(tpl, img_path, width=Mm(140))
    else:
        ctx["id_photo"] = ""  # keep placeholder empty if not found
    tpl.render(ctx)

    # -> PDF
    buf = io.BytesIO()
    tpl.save(buf)
    buf.seek(0)
    pdf_bytes = _docx_to_pdf_bytes(buf.getvalue())
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")

@reports_docx_bp.post("/<int:report_id>/photo-id/render-docx")
def photo_id_render_docx(report_id: int):
    payload    = request.get_json(silent=True) or {}
    insured_id = payload.get("insured_id") or 0

    id_date  = (payload.get("id_photo_date_text") or payload.get("id_photo_date") or "").strip()
    id_time  = (payload.get("id_photo_time") or "").strip()
    id_city  = (payload.get("id_photo_city") or "").strip()
    id_place = (payload.get("id_photo_place") or "").strip()

    # Source selected in the "תמונת זיהוי" widget (may be full path / URL / data:)
    id_src = (payload.get("id_photo_src") or "").strip()

    # Also consider selected_photos (client sends [basename])
    names = request.args.getlist("selected_photos[]") or request.args.getlist("selected_photos") or []
    base_name = names[0] if names else None

    # If we somehow got the route name 'serve' as a "filename", ignore it
    if base_name and base_name.lower() == "serve":
        base_name = None

    # Prefer the explicit server-side filename; fall back to id_src only if needed
    key = base_name or id_src
    img_path = _resolve_photo_id_image(insured_id, report_id, key)


    current_app.logger.info(
        "[PhotoID][docx] report=%s insured=%s src=%r base=%r -> %r",
        report_id, insured_id, id_src, base_name, img_path
    )

    ctx = get_report_context(report_id, insured_id=insured_id)
    place_str = ", ".join(v for v in (id_place, id_city) if v)
    ctx.update({
        "id_date":  id_date or _iso_to_dots(ctx.get("ctx", {}).get("activity_date", "")),
        "id_time":  id_time,
        "id_place": place_str,
    })

    template_path = os.path.join(current_app.root_path, "docx_templates", "menora_photo_id.docx")
    current_app.logger.info("[PhotoID][docx] template: %s", template_path)

    tpl = DocxTemplate(template_path)
    if img_path:
      ctx["id_photo"] = InlineImage(tpl, img_path, width=Mm(140))
    else:
      ctx["id_photo"] = ""
    tpl.render(ctx)

    # save to instance/generated_reports
    out_dir = os.path.join(current_app.instance_path, "generated_reports")
    os.makedirs(out_dir, exist_ok=True)
    stamp    = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{report_id}_{stamp}.docx"
    abs_path = os.path.join(out_dir, filename)
    tpl.save(abs_path)

    docx_url = url_for("generated_reports", filename=filename)
    current_app.logger.info("[PhotoID][docx] saved: %s -> %s", abs_path, docx_url)

    return jsonify({"ok": True, "docx_url": docx_url})




# ================== /PHOTO ID: dedicated endpoints (server only) =======================














