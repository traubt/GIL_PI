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
    overrides = {
        "activity_date": request.args.get("activity_date", ""),
        "surv_place":    request.args.get("surv_place", ""),
        "surv_city":     request.args.get("surv_city",  ""),
        "injury_type":   request.args.get("injury_type", ""),
    }
    ctx = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

    # --- template path ---
    tmpl_key = (request.args.get("template", "siudi") or "siudi").strip().lower()
    template_path = load_template_docx(map_template_key(tmpl_key))  # full path
    current_app.logger.info("[DOCX] Using template: %s", template_path)

    tpl = DocxTemplate(template_path)

    # --- collect selected files (names) -> absolute paths ---
    selected = request.args.getlist("selected_photos[]") or request.args.getlist("selected_photos")
    selected = [os.path.basename(n) for n in selected if n]
    case_id   = (request.args.get("insured_id") or request.args.get("case_id") or "").strip()
    rep_id    = str(report_id)
    media_root = current_app.config.get("REPORT_MEDIA_DIR", os.path.join(current_app.instance_path, "report_media"))

    def resolve_one(name: str) -> str | None:
        # exact
        p = os.path.join(media_root, case_id, rep_id, name)
        if os.path.isfile(p): return p
        # fallback search under case folder
        root_case = os.path.join(media_root, case_id)
        for root, _d, files in os.walk(root_case):
            if name in files:
                return os.path.join(root, name)
        current_app.logger.warning("[PHOTOS] not found: %s", name)
        return None

    paths = [p for n in selected if (p := resolve_one(n))]
    # fallback: include all images in the report folder
    if not paths:
        folder = os.path.join(media_root, case_id, rep_id)
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                    paths.append(os.path.join(folder, fn))

    # --- classify by orientation (use real pixel size, not EXIF orientation) ---
    from PIL import Image
    lands, ports = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                w, h = im.size
            if w >= h:
                lands.append(p)
            else:
                ports.append(p)
        except Exception as e:
            current_app.logger.warning("[PHOTOS] failed to open %s: %s", p, e)

    # --- sizing: keep your landscape width, choose portrait width so 2 fit per line ---
    LAND_W = Mm(120)  # as before
    PORT_W = Mm(76)   # ~76 mm + ~10–14 mm gap fits two across 165 mm text width

    land_images = [InlineImage(tpl, p, width=LAND_W) for p in lands]

    # chunk portraits into pairs (left, right_or_None)
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

    # NBSP gap between two inline images keeps them visually separated and prevents collapse
    gap = "\u00A0" * 8  # 8 NBSPs (~small gutter). Adjust to taste.

    # build final context
    ctx.update({
        "land_images": land_images,
        "port_rows":   port_rows,   # list of (left_img, right_img_or_None)
        "gap":         gap,
    })

    # render -> DOCX bytes
    buf = io.BytesIO()
    tpl.render(ctx)
    tpl.save(buf)
    docx_bytes = buf.getvalue()

    # DOCX -> PDF (your existing converter)
    pdf_bytes = _docx_to_pdf_bytes(docx_bytes)
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")




# ==== "Word הורד" – render a .docx and give a URL to download ====
@reports_docx_bp.route("/<int:report_id>/render-docx", methods=["POST"])
def render_docx_download(report_id: int):
    import io, os, datetime, json
    from PIL import Image
    from flask import current_app, request, jsonify, url_for
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm

    payload = request.get_json(silent=True) or {}

    insured_id   = payload.get("insured_id")
    overrides = {
        "activity_date": payload.get("activity_date", ""),
        "surv_place":    payload.get("surv_place", ""),
        "surv_city":     payload.get("surv_city",  ""),
        "injury_type":   payload.get("injury_type", ""),
    }
    ctx = get_report_context(report_id, insured_id=insured_id, overrides=overrides)

    # --- template path ---
    tmpl_key = (payload.get("template") or "siudi").strip().lower()
    template_path = load_template_docx(map_template_key(tmpl_key))
    current_app.logger.info("[DOCX] Using template: %s", template_path)

    tpl = DocxTemplate(template_path)

    # --- collect selected names from payload ---
    names = payload.get("selected_photos") or []
    if not names and isinstance(payload.get("photos"), list):
        # optional detailed objects: [{'name': '...'}, ...]
        names = [os.path.basename(p.get("name", "")) for p in payload["photos"] if p.get("name")]

    names = [os.path.basename(n) for n in names if n]

    # --- resolve to absolute paths ---
    case_id   = str(insured_id or payload.get("case_id", "")).strip()
    rep_id    = str(report_id)
    media_root = current_app.config.get("REPORT_MEDIA_DIR",
        os.path.join(current_app.instance_path, "report_media")
    )

    def resolve_one(name: str) -> str | None:
        exact = os.path.join(media_root, case_id, rep_id, name)
        if os.path.isfile(exact): return exact
        # fallback search under case folder
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
    LAND_W = Mm(120)   # landscape width
    PORT_W = Mm(76)    # portrait width so two fit per line

    land_images = [InlineImage(tpl, p, width=LAND_W) for p in lands]

    # chunk portraits into (left, right_or_None)
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

    gap = "\u00A0" * 8  # NBSP gutter between two inline images

    # merge into context
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

    # public URL via your url_rule('generated_reports', ...)
    docx_url = url_for("generated_reports", filename=filename)

    return jsonify({"ok": True, "docx_url": docx_url})


# ===================== PHOTO ID: dedicated endpoints (server only) =====================
# Uses your existing helpers:
#   - reports_docx_bp (Blueprint)
#   - get_report_context(report_id, insured_id=..., overrides=None)
#   - load_template_docx(template_filename) -> absolute path
#   - _docx_to_pdf_bytes(docx_bytes) -> bytes

@reports_docx_bp.get("/<int:report_id>/photo-id/preview-pdf")
def photo_id_preview_pdf(report_id: int):
    """
    Preview PDF for 'menora_photo_id.docx'.

    Query params (send what the UI shows; no special formatting required):
      insured_id
      id_photo_date_text   -> the visible date text (e.g., '04/11/2025' or '4.11.2025')
      id_photo_date        -> optional ISO fallback ('YYYY-MM-DD') if you don't send *_text
      id_photo_time        -> pass-through (e.g., '12:33 PM') — embedded as-is
      id_photo_city
      id_photo_place
      id_photo_src         -> data URL | absolute path | basename under REPORT_MEDIA_DIR/<insured>/<report>/**
    """
    from flask import request, current_app, send_file
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm
    import os, io, re, base64, tempfile

    # ---- local helpers (kept inside the route to avoid global changes) ----
    def _media_root() -> str:
        return current_app.config.get(
            "REPORT_MEDIA_DIR",
            os.path.join(current_app.instance_path, "report_media"),
        )

    def _resolve_one_image(src: str, insured_id: int | None, report_id: int) -> str | None:
        """data URL -> temp file; absolute path; else search by basename under media folders."""
        if not src:
            return None
        if src.startswith("data:"):
            m = re.match(r"data:image/(png|jpe?g|webp);base64,(.+)$", src, re.I)
            if not m:
                return None
            ext = "jpg" if m.group(1).lower().startswith("jp") else m.group(1).lower()
            fd, path = tempfile.mkstemp(prefix="photo_id_", suffix=f".{ext}")
            os.write(fd, base64.b64decode(m.group(2))); os.close(fd)
            return path
        if os.path.isabs(src) and os.path.isfile(src):
            return src
        base = os.path.basename(src)
        roots = []
        root = _media_root()
        if insured_id:
            roots.append(os.path.join(root, str(insured_id), str(report_id)))
            roots.append(os.path.join(root, str(insured_id)))
        else:
            roots.append(root)
        for r0 in roots:
            if os.path.isdir(r0):
                for r, _d, files in os.walk(r0):
                    if base in files:
                        return os.path.join(r, base)
        return None

    def _iso_to_dots_fallback(iso_or_text: str) -> str:
        """
        If the string looks like ISO 'YYYY-MM-DD', convert to 'D.MM.YYYY'.
        Otherwise, return as-is (we trust the UI).
        """
        s = (iso_or_text or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            y, m, d = s.split("-")
            return f"{int(d)}.{m}.{y}"
        return s

    # ---- collect inputs exactly as sent by the UI ----
    insured_id = request.args.get("insured_id", type=int)
    date_text  = (request.args.get("id_photo_date_text") or "").strip()
    date_iso   = (request.args.get("id_photo_date") or "").strip()
    time_text  = (request.args.get("id_photo_time") or "").strip()     # pass-through
    city       = (request.args.get("id_photo_city") or "").strip()
    place_only = (request.args.get("id_photo_place") or "").strip()
    photo_src  = (request.args.get("id_photo_src") or "").strip()
    place_text = " ".join(p for p in [city, place_only] if p).strip()

    # ---- base context from your existing helper ----
    ctx = get_report_context(report_id, insured_id=insured_id)

    # Date text strategy:
    # 1) If UI gave us id_photo_date_text, use it as-is.
    # 2) Else if UI sent id_photo_date (ISO), convert locally to D.MM.YYYY once.
    # 3) Else, fall back to ctx.activity_date (already whatever your app uses) and apply same fallback.
    if not date_text:
        date_text = date_iso or ctx.get("ctx", {}).get("activity_date") or ""
        date_text = _iso_to_dots_fallback(date_text)

    # Merge the fields expected by the template
    ctx.update({
        "id_date":  date_text,     # final string for the template (no more formatting)
        "id_time":  time_text,     # pass-through string
        "id_place": place_text,
    })

    template_path = load_template_docx("menora_photo_id.docx")
    tpl = DocxTemplate(template_path)

    resolved = _resolve_one_image(photo_src, insured_id, report_id)
    ctx["id_photo"] = InlineImage(tpl, resolved, width=Mm(120)) if resolved else ""

    # Render -> PDF
    buf = io.BytesIO(); tpl.render(ctx); tpl.save(buf)
    pdf_bytes = _docx_to_pdf_bytes(buf.getvalue())
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")


@reports_docx_bp.post("/<int:report_id>/photo-id/render-docx")
def photo_id_render_docx(report_id: int):
    """
    Generate DOCX for 'menora_photo_id.docx'.

    JSON body (send what the UI shows; no special formatting required):
      insured_id
      id_photo_date_text   -> preferred (visible text)
      id_photo_date        -> optional ISO fallback
      id_photo_time        -> pass-through (e.g., '12:33 PM')
      id_photo_city
      id_photo_place
      id_photo_src
    """
    from flask import request, current_app, jsonify, url_for
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm
    import os, re, base64, tempfile, io, datetime as _dt

    # same local helpers as preview
    def _media_root() -> str:
        return current_app.config.get(
            "REPORT_MEDIA_DIR",
            os.path.join(current_app.instance_path, "report_media"),
        )

    def _resolve_one_image(src: str, insured_id: int | None, report_id: int) -> str | None:
        if not src:
            return None
        if src.startswith("data:"):
            m = re.match(r"data:image/(png|jpe?g|webp);base64,(.+)$", src, re.I)
            if not m: return None
            ext = "jpg" if m.group(1).lower().startswith("jp") else m.group(1).lower()
            fd, path = tempfile.mkstemp(prefix="photo_id_", suffix=f".{ext}")
            os.write(fd, base64.b64decode(m.group(2))); os.close(fd)
            return path
        if os.path.isabs(src) and os.path.isfile(src):
            return src
        base = os.path.basename(src)
        roots = []
        root = _media_root()
        if insured_id:
            roots.append(os.path.join(root, str(insured_id), str(report_id)))
            roots.append(os.path.join(root, str(insured_id)))
        else:
            roots.append(root)
        for r0 in roots:
            if os.path.isdir(r0):
                for r, _d, files in os.walk(r0):
                    if base in files:
                        return os.path.join(r, base)
        return None

    def _iso_to_dots_fallback(iso_or_text: str) -> str:
        s = (iso_or_text or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            y, m, d = s.split("-")
            return f"{int(d)}.{m}.{y}"
        return s

    payload    = request.get_json(silent=True) or {}
    insured_id = payload.get("insured_id")

    date_text  = (payload.get("id_photo_date_text") or "").strip()
    date_iso   = (payload.get("id_photo_date") or "").strip()
    time_text  = (payload.get("id_photo_time") or "").strip()
    city       = (payload.get("id_photo_city") or "").strip()
    place_only = (payload.get("id_photo_place") or "").strip()
    photo_src  = (payload.get("id_photo_src") or "").strip()
    place_text = " ".join(p for p in [city, place_only] if p).strip()

    ctx = get_report_context(report_id, insured_id=insured_id)

    if not date_text:
        date_text = date_iso or ctx.get("ctx", {}).get("activity_date") or ""
        date_text = _iso_to_dots_fallback(date_text)

    ctx.update({
        "id_date":  date_text,     # final date string
        "id_time":  time_text,     # pass-through
        "id_place": place_text,
    })

    template_path = load_template_docx("menora_photo_id.docx")
    tpl = DocxTemplate(template_path)

    resolved = _resolve_one_image(photo_src, insured_id, report_id)
    ctx["id_photo"] = InlineImage(tpl, resolved, width=Mm(120)) if resolved else ""

    out_dir = os.path.join(current_app.instance_path, "generated_reports")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"photo_id_{report_id}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    abs_path = os.path.join(out_dir, filename)

    tpl.render(ctx)
    tpl.save(abs_path)

    try:
        href = url_for("generated_reports", filename=filename)
    except Exception:
        href = f"/generated_reports/{filename}"

    return jsonify({"ok": True, "docx_url": href})
# ================== /PHOTO ID: dedicated endpoints (server only) =======================














