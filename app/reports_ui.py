# app/reports_ui.py
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from app import db
from app.models import GilInsured, GilReport
import io, json
from datetime import datetime, date
import subprocess, tempfile, os
from urllib.parse import urljoin

reports_ui_bp = Blueprint('reports_ui', __name__, url_prefix='/reports')


# ---------- helpers ----------

def _compute_reference(ref_number: str | None, version_no: int) -> str:
    base = (ref_number or "00000").strip()
    return base if (version_no or 0) <= 0 else f"{base}.{version_no}"

def _template_key(insurance: str | None, report_type: str) -> str:
    ins = (insurance or '').strip() or 'כללי'
    return f"{ins}_{report_type}".lower()

def _he_date(iso_date: str | None) -> str:
    """YYYY-MM-DD -> '30 בספטמבר 2025' (or today if missing/invalid)."""
    if not iso_date:
        dt = date.today()
    else:
        try:
            y, m, d = map(int, iso_date.split('-'))
            dt = date(y, m, d)
        except Exception:
            dt = date.today()
    months = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]
    return f"{dt.day} ב{months[dt.month-1]} {dt.year}"

def _ddmmyyyy(iso_date: str | None) -> str:
    """YYYY-MM-DD -> DD.MM.YYYY (empty if missing/invalid)."""
    try:
        y, m, d = map(int, (iso_date or '').split('-'))
        return f"{d:02d}.{m:02d}.{y}"
    except Exception:
        return ""

def _get_first_nonempty(obj, *names, default=""):
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v not in (None, "", "NULL"):
                return v
    return default

def _wkhtmltopdf_bytes(body_html: str, header_html: str, footer_html: str) -> bytes:
    """Render HTML string to PDF bytes using wkhtmltopdf with header/footer HTMLs."""
    wkhtml = current_app.config.get('WKHTMLTOPDF_CMD')
    if not wkhtml or not os.path.exists(wkhtml):
        raise RuntimeError(f"wkhtmltopdf not found at: {wkhtml!r}")

    # temp files: body, header, footer
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as fbody, \
         tempfile.NamedTemporaryFile(suffix=".html", delete=False) as fhead, \
         tempfile.NamedTemporaryFile(suffix=".html", delete=False) as ffoot:
        fbody.write(body_html.encode('utf-8'));  fbody.flush()
        fhead.write(header_html.encode('utf-8')); fhead.flush()
        ffoot.write(footer_html.encode('utf-8')); ffoot.flush()
        body_path, head_path, foot_path = fbody.name, fhead.name, ffoot.name

    try:
        # margins sized for your header/footer PNGs
        cmd = [
            wkhtml,
            "--enable-local-file-access",
            "--quiet",
            "--margin-top", "46",
            "--margin-bottom", "30",  # ↓ was 44 — tighter footer area
            "--header-html", head_path,
            "--header-spacing", "0",
            "--footer-html", foot_path,
            "--footer-spacing", "0",
            body_path, "-"
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8', 'ignore'))
        return proc.stdout
    finally:
        for p in (body_path, head_path, foot_path):
            try: os.remove(p)
            except Exception: pass


# ---------- UI pages ----------

@reports_ui_bp.route('/editor', methods=['GET'])
def reports_editor():
    insureds = db.session.query(GilInsured).order_by(GilInsured.last_name.asc()).all()
    return render_template('reports/editor.html', insureds=insureds)


# ---------- Draft/Finalize APIs (unchanged behaviour) ----------

@reports_ui_bp.route('/save_draft', methods=['POST'])
def save_draft():
    payload = request.get_json(silent=True) or {}
    report_id  = payload.get('report_id')
    insured_id = payload.get('insured_id')
    report_type = payload.get('report_type', 'TRACKING')

    insured = db.session.get(GilInsured, insured_id) if insured_id else None

    if report_id:
        rpt = db.session.get(GilReport, int(report_id))
        if not rpt:
            return jsonify({'status': 'error', 'message': 'Report not found'}), 404
        if not insured and rpt.case_id:
            insured = db.session.get(GilInsured, rpt.case_id)
    else:
        if not insured:
            return jsonify({'status': 'error', 'message': 'Missing insured_id'}), 400
        rpt = GilReport(
            case_id=insured.id,
            report_type=report_type,
            template_key=_template_key(getattr(insured, 'insurance', None), report_type),
            status='Draft',
            version_no=payload.get('version_no', 0) or 0,
        )
        db.session.add(rpt)

    rpt.title = payload.get('title') or rpt.title
    rpt.editor_json = json.dumps(payload, ensure_ascii=False)

    ref_number = _get_first_nonempty(insured or object(), 'ref_number','ref', default=None)
    rpt.reference_no = _compute_reference(ref_number, int(rpt.version_no or 0))
    rpt.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'status': 'ok',
        'report_id': rpt.id,
        'status_str': rpt.status,
        'version_no': rpt.version_no,
        'reference_no': rpt.reference_no,
    })


@reports_ui_bp.route('/finalize', methods=['POST'])
def finalize():
    action = request.form.get('action')
    report_id = request.form.get('report_id') or request.args.get('report_id')
    if not report_id:
        return jsonify({'status': 'error', 'message': 'Missing report_id'}), 400

    rpt = db.session.get(GilReport, int(report_id))
    if not rpt:
        return jsonify({'status': 'error', 'message': 'Report not found'}), 404

    insured = db.session.get(GilInsured, rpt.case_id)
    ref_number = _get_first_nonempty(insured, 'ref_number', 'ref', default=None)

    if action == 'version':
        rpt.version_no = (rpt.version_no or 0) + 1
        rpt.status = 'Revised'
        rpt.reference_no = _compute_reference(ref_number, rpt.version_no)
    elif action == 'save_to_dropbox':
        pass
    elif action == 'send_to_insurer':
        rpt.status = 'Submitted'
    elif action == 'finalize':
        rpt.status = 'Final'
        rpt.reference_no = _compute_reference(ref_number, int(rpt.version_no or 0))

    db.session.commit()
    return jsonify({
        'status': 'ok',
        'status_str': rpt.status,
        'version_no': rpt.version_no,
        'reference_no': rpt.reference_no
    })


# ---------- Preview (header/footer via wkhtmltopdf) ----------

@reports_ui_bp.route('/preview', methods=['POST'])
def preview():
    payload     = request.get_json(silent=True) or {}
    insured_id  = payload.get('insured_id')
    report_type = payload.get('report_type', 'TRACKING')

    insured = db.session.get(GilInsured, insured_id) if insured_id else None
    if not insured:
        return jsonify({'error': 'missing insured'}), 400

    insurer     = (insured.insurance or "").strip()
    claim_type  = (insured.claim_type or "").strip()

    # refs & dates
    reference_no     = payload.get('reference_no') or _get_first_nonempty(insured, 'ref_number','ref', default="00000")
    report_date_text = _he_date(payload.get('report_date'))
    activity_date_fmt= _ddmmyyyy(payload.get('activity_date'))

    # body fields
    full_name    = f"{_get_first_nonempty(insured, 'last_name')} {_get_first_nonempty(insured, 'first_name')}".strip()
    address      = f"{_get_first_nonempty(insured, 'city')} {_get_first_nonempty(insured, 'address')}".strip()
    id_number    = _get_first_nonempty(insured, 'id_number')
    claim_number = _get_first_nonempty(insured, 'claim_number', 'claim_no', 'claim', 'claimnumber')
    injury_type  = "מצב סיעודי"

    birth_year = ""
    try:
        bd = insured.birth_date
        if bd:
            birth_year = bd[:4] if isinstance(bd, str) else str(bd.year)
    except Exception:
        pass

    # Static URLs
    base_url   = request.url_root
    header_url = urljoin(base_url, "static/report_header_gil.png")
    footer_url = urljoin(base_url, "static/report_footer_gil.png")

    # Body (no header/footer inside)
    if insurer == "מנורה" and "סיעוד" in claim_type and report_type == "TRACKING":
        body_html = render_template(
            "reports/templates/menora_siudi_tracking.html",
            full_name=full_name, address=address,
            id_number=id_number, claim_number=claim_number,
            injury_type=injury_type, birth_year=birth_year,
            activity_date=activity_date_fmt,   # DD.MM.YYYY here
        )
    else:
        body_html = f"""<!doctype html><meta charset="utf-8"><body dir="rtl" style="font-family:Arial;padding:40px">
        <h3>תצוגה מקדימה</h3>
        <p>טרם קיימת תבנית לדגם זה.</p>
        <p><b>חברה:</b> {insurer} · <b>סוג תביעה:</b> {claim_type} · <b>סוג דו"ח:</b> {report_type}</p></body>"""

    # Header HTML: top bar image + row with left (date/ref) & right (insurer block)
    header_html = f"""<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8">
    <style>
      html,body{{margin:0;padding:0;font-family:'Assistant',Arial,sans-serif;color:#111;}}
      .wrap{{position:relative;}}
      .bar img{{width:100%;display:block;}}
      /* compact info band under the bar */
      .info{{position:relative;height:48px;}}
      .left,.right{{position:absolute;top:6px;line-height:1.35;font-size:12pt;}}
      .left{{left:20mm;font-weight:700; text-align:left;}}   /* DATE + REF pinned to the left */
      .right{{right:12mm;text-align:right;}}                 /* "לכבוד..." pinned to the far right */
      .right b{{font-weight:700}}
    </style>
    <body>
      <div class="wrap">
        <div class="bar"><img src="{header_url}" alt=""></div>
        <div class="info">
          <div class="left">
            <div>{report_date_text}</div>
            <div>מספרנו: {reference_no}</div>
          </div>
          <div class="right">
            <div>לכבוד</div>
            <div><b>מנורה – חברה לביטוח</b></div>
            <div>מחלקת תביעות סיעודי</div>
          </div>
        </div>
      </div>
    </body></html>"""

    # Footer HTML: contact bar image + small page number inside black square
    footer_html = f"""<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8">
    <style>
      html,body{{margin:0;padding:0;font-family:'Assistant',Arial,sans-serif;}}
      /* Footer canvas */
      .foot{{position:relative; height:50px; box-sizing:border-box;}}

      /* PAGE NUMBER — fixed to bottom-left, perfectly centered */
      .pageno{{
        position:absolute; left:12mm; bottom:2px;
        width:12mm; height:12mm;
        background:#333; color:#fff; border-radius:3px;
        /* no flex here */
      }}
      .pageno .page{{
        position:absolute; left:50%; top:50%;
        transform:translate(-50%, -50%);   /* dead-center */
        font-size:10pt; font-weight:700; line-height:1; margin:0; padding:0;
      }}

      /* GIL STRIP — fixed to bottom-right */
      .brand{{ position:absolute; right:12mm; bottom:0; }}
      .brand img{{ height:40px; width:auto; display:block; }}
    </style>

    <body onload="subst()">
      <div class="foot">
        <div class="pageno"><span class="page"></span></div>
        <div class="brand"><img src="{footer_url}" alt=""></div>
      </div>

      <script>
      function subst(){{
          var vars={{}}, q=window.location.search.substring(1).split('&');
          for (var i=0;i<q.length;i++) {{
              var p=q[i].split('=',2);
              vars[p[0]] = decodeURIComponent(p[1]||'');
          }}
          var els=document.getElementsByClassName('page');
          for (var j=0;j<els.length;j++) els[j].textContent = vars.page || '';
      }}
      </script>
    </body></html>"""

    pdf_bytes = _wkhtmltopdf_bytes(
        body_html,
        header_html,
        footer_html
    )

    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=False, download_name='preview.pdf')


# --- Add these imports at top of reports_ui.py ---
import os, uuid
from flask import current_app
from werkzeug.utils import secure_filename
from app.models import GilInsured
from app.dropbox_util import dbx, build_dropbox_folder_path, list_case_images


ALLOWED_EXTS = {"jpg", "jpeg", "png"}

def _uploads_root():
    root = os.path.join(current_app.root_path, "static", "uploads", "reports")
    os.makedirs(root, exist_ok=True)
    return root

def _public_url_for(rel_path: str) -> str:
    # rel_path like 'uploads/reports/abcd/pic.jpg'
    rel_norm = rel_path.replace("\\", "/")  # <- do the replace outside the f-string (Py 3.11 safe)
    return f"/static/{rel_norm}"


# app/reports_ui.py (only the dropbox branch inside list_photos)
@reports_ui_bp.route('/photos/list', methods=['POST'])
def list_photos():
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "").strip()
    images = []

    if source == "dropbox":
        insured_id = data.get("insured_id")
        if not insured_id:
            return jsonify({"images": []})

        insured = db.session.get(GilInsured, int(insured_id))
        if not insured:
            return jsonify({"images": []})

        # Build the insured’s case root folder
        case_root = build_dropbox_folder_path(
            insured.insurance or "",
            insured.claim_type or "",
            insured.last_name or "",
            insured.first_name or "",
            insured.id_number or "",
            insured.claim_number or "",
        )

        if case_root:
            # -> this looks specifically in '<case_root>/תמונות'
            images = list_case_images(dbx, case_root)

        return jsonify({"images": images})

    # ... your existing 'local' branch remains unchanged ...
    # (returns local uploaded images for this editor session)

    return jsonify({"images": []})


@reports_ui_bp.route('/photos/upload', methods=['POST'])
def upload_photos():
    """
    FormData: files[] (multiple), local_token
    Saves under /static/uploads/reports/<token>/filename and returns URLs.
    """
    token = request.form.get("local_token") or str(uuid.uuid4())
    files = request.files.getlist("files[]") or request.files.getlist("files")
    saved = []

    if not files:
        return jsonify({"token": token, "images": []})

    session_dir = os.path.join(_uploads_root(), token)
    os.makedirs(session_dir, exist_ok=True)

    for f in files:
        if not f or not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTS:
            continue
        safe = secure_filename(f.filename)
        # avoid collisions
        base, extn = os.path.splitext(safe)
        final = f"{base}_{uuid.uuid4().hex[:6]}{extn}"
        out_path = os.path.join(session_dir, final)
        f.save(out_path)
        rel = os.path.join("uploads", "reports", token, final)
        saved.append({"name": final, "url": _public_url_for(rel)})

    return jsonify({"token": token, "images": saved})

