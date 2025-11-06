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
        "age":          _calc_age(ins.birth_date),
        "injury_type":  getattr(ins, "injury_type", "") or "",
    }

def get_report_context(report_id: int, *, insured_id: int | None = None, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    db_fields  = _fetch_insured_row(insured_id) if insured_id else {}
    raw_date   = overrides.get("activity_date", "")
    act_iso    = _to_iso(raw_date) or raw_date

    ctx_fields = {
        "activity_date":       act_iso,
        "activity_date_dots":  _iso_to_dots(act_iso),
        "surv_place":          overrides.get("surv_place", ""),
        "surv_city":           overrides.get("surv_city",  ""),
        "injury_type":         overrides.get("injury_type", ""),
    }

    lex = _gender_lex(db_fields.get("gender"))

    return {
        "db": db_fields,
        "ctx": ctx_fields,
        "lex": lex,           # <— NEW
        "now": _now_hebrew(),
    }




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
from contextlib import contextmanager

@contextmanager
def _tmpdir(prefix="report_img_"):
    td = tempfile.TemporaryDirectory(prefix=prefix)
    try:
        yield td.name
    finally:
        td.cleanup()

def _detect_orientation(path: str) -> str:
    """
    Return 'portrait' if the visual height is meaningfully larger than width,
    after correcting EXIF rotation; otherwise 'landscape'.
    Uses a tolerance so near-square shots don’t get misclassified.
    """
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            # treat as portrait if height is at least 10% greater than width
            return "portrait" if (h / max(1, w)) >= 1.10 else "landscape"
    except Exception:
        return "landscape"


def _resize_copy(src: str, dst: str, max_w: int, max_h: int, quality: int = 82):
    """Resize into dst (JPEG) with EXIF rotation, keep aspect."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_w, max_h), Image.LANCZOS)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(dst, format="JPEG",
                quality=quality, optimize=True, progressive=True, subsampling="4:2:0")

def _preprocess_for_docx(tmpdir: str, paths: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for idx, p in enumerate(paths):
        orient = _detect_orientation(p)
        # ↓ smaller caps = smaller files
        max_w, max_h = ((700, 1100) if orient == "portrait" else (1400, 900))
        dst = os.path.join(tmpdir, f"img_{idx:03d}.jpg")
        try:
            _resize_copy(p, dst, max_w, max_h, quality=80)
            out.append((dst, orient))
        except Exception as e:
            current_app.logger.warning("[PREPROC] failed %s: %s; using original", p, e)
            out.append((p, orient))
    return out


def _report_media_root() -> str:
    return current_app.config.get(
        "REPORT_MEDIA_DIR",
        os.path.join(current_app.instance_path, "report_media")
    )

# ====== FULL ROUTE: /reports/<id>/preview-pdf  ===============================
@reports_docx_bp.route("/<int:report_id>/preview-pdf", methods=["GET"])
def preview_docx_as_pdf(report_id: int):
    insured_id = request.args.get("insured_id", type=int)
    overrides = {
        "activity_date": request.args.get("activity_date", ""),
        "surv_place":    request.args.get("surv_place", ""),
        "surv_city":     request.args.get("surv_city",  ""),
        "injury_type":   request.args.get("injury_type", ""),
    }
    context = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

    # template
    tmpl_key = request.args.get("template", "tracking")
    template_path = load_template_docx(map_template_key(tmpl_key))
    tpl = DocxTemplate(template_path)

    # selected names (support both [] and non-[] styles)
    selected = request.args.getlist("selected_photos[]") or request.args.getlist("selected_photos")
    selected = [os.path.basename(n) for n in selected if n]

    case_id   = (request.args.get("insured_id") or request.args.get("case_id") or "").strip()
    rep_id    = str(report_id)
    media_root = _report_media_root()

    def resolve_one(name: str) -> str | None:
        exact = os.path.join(media_root, case_id, rep_id, name)
        if os.path.isfile(exact):
            return exact
        # fallback: anywhere under the case folder
        case_root = os.path.join(media_root, case_id)
        if os.path.isdir(case_root):
            for root, _dirs, files in os.walk(case_root):
                if name in files:
                    return os.path.join(root, name)
        current_app.logger.warning("[PHOTOS] not found: %s", name)
        return None

    paths = [p for n in selected if (p := resolve_one(n))]
    if not paths:
        # fallback to all images in current report folder
        folder = os.path.join(media_root, case_id, rep_id)
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith((".jpg",".jpeg",".png",".webp",".bmp",".gif")):
                    paths.append(os.path.join(folder, fn))

    # preprocess (rotate/resize -> temp JPEGs) and build InlineImages with fixed widths
    with _tmpdir() as td:
        proc_items = _preprocess_for_docx(td, paths)
        LAND_W, PORT_W = Mm(120), Mm(42)  # fixed visual sizes in the DOCX
        images = []
        for p, orient in proc_items:
            width = PORT_W if orient == "portrait" else LAND_W
            images.append(InlineImage(tpl, p, width=width))

        context["photo_s3"]  = images[0] if images else ""
        context["photos_s3"] = images

        # render to DOCX bytes while temp files still exist
        buf = io.BytesIO()
        tpl.render(context)
        tpl.save(buf)
        docx_bytes = buf.getvalue()

    # convert DOCX bytes -> PDF bytes (your existing helper)
    pdf_bytes = _docx_to_pdf_bytes(docx_bytes)
    return send_file(io.BytesIO(pdf_bytes),
                     mimetype="application/pdf",
                     download_name="preview.pdf")

@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def render_docx_download(report_id: int):
    try:
        body = request.get_json(silent=True) or {}

        insured_id = body.get("insured_id", None)
        overrides = {
            "activity_date": body.get("activity_date", ""),
            "surv_place":    body.get("surv_place", ""),
            "surv_city":     body.get("surv_city",  ""),
            "injury_type":   body.get("injury_type", ""),
        }
        context = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

        # template
        tmpl_key      = (body.get("template") or "tracking").lower()
        template_path = load_template_docx(map_template_key(tmpl_key))
        tpl = DocxTemplate(template_path)

        # -------- collect selected photo names (several payload shapes are supported) --------
        # A) explicit names list (same as preview)
        selected = body.get("selected_photos") or []

        # B) or a 'photos' array of objects from the client picker:
        #    [{name, selected, orientation, ...}]
        if not selected and isinstance(body.get("photos"), list):
            selected = [os.path.basename(p["name"])
                        for p in body["photos"]
                        if isinstance(p, dict) and p.get("selected", True) and p.get("name")]

        # sanitize
        selected = [os.path.basename(n) for n in selected if n]

        case_id   = str(body.get("insured_id") or body.get("case_id") or "").strip()
        rep_id    = str(report_id)
        media_root = current_app.config.get(
            "REPORT_MEDIA_DIR",
            os.path.join(current_app.instance_path, "report_media")
        )

        def resolve_one(name: str) -> str | None:
            exact = os.path.join(media_root, case_id, rep_id, name)
            if os.path.isfile(exact):
                return exact
            # fallback: search anywhere under the case folder
            case_root = os.path.join(media_root, case_id)
            if os.path.isdir(case_root):
                for root, _dirs, files in os.walk(case_root):
                    if name in files:
                        return os.path.join(root, name)
            current_app.logger.warning("[PHOTOS] not found: %s", name)
            return None

        paths = [p for n in selected if (p := resolve_one(n))]

        # fallback: if none explicitly selected/resolved, include all images for this report
        if not paths:
            folder = os.path.join(media_root, case_id, rep_id)
            if os.path.isdir(folder):
                for fn in sorted(os.listdir(folder)):
                    if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                        paths.append(os.path.join(folder, fn))

        # -------- preprocess & size like preview (EXIF rotate + resize to temp JPEGs) --------
        with _tmpdir() as td:
            proc_items = _preprocess_for_docx(td, paths)

            # keep same page presence as preview
            LAND_W = Mm(120)
            PORT_W = Mm(42)  # smaller so portraits don’t eat a whole page

            images = []
            for p, orient in proc_items:
                width = PORT_W if orient == "portrait" else LAND_W
                images.append(InlineImage(tpl, p, width=width))

            # section 3 – one or many
            context["photo_s3"]  = images[0] if images else ""
            context["photos_s3"] = images

            # render DOCX to bytes while temp files exist
            buf = io.BytesIO()
            tpl.render(context)
            tpl.save(buf)
            docx_bytes = buf.getvalue()

        # -------- save to disk and return a link (JSON) --------
        # make sure OUTPUT_DIR / ensure_output_dir() exist in your file (as before)
        ensure_output_dir()
        fname = f"report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        out_path = os.path.join(OUTPUT_DIR, fname)
        with open(out_path, "wb") as f:
            f.write(docx_bytes)

        return jsonify({"ok": True, "docx_url": f"/reports/{report_id}/download/{fname}"}), 200

    except Exception as e:
        current_app.logger.exception("render-docx failed")
        # keeps the client from trying to JSON-parse an HTML traceback
        return jsonify({"ok": False, "error": str(e)}), 500










