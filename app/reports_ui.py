# routes/reports_ui.py
from flask import Blueprint, render_template, request, jsonify, send_file
from app import db
# import your insured model
from app.models import GilInsured # adjust import to your project
import io

reports_ui_bp = Blueprint('reports_ui', __name__, url_prefix='/reports')

@reports_ui_bp.route('/editor', methods=['GET'])
def reports_editor():
    # pre-load insureds for the select
    insureds = db.session.query(GilInsured).order_by(GilInsured.last_name.asc()).all()
    return render_template('reports/editor.html', insureds=insureds)

# ---- STUB: live-draft save (no DB yet; returns OK)
@reports_ui_bp.route('/save_draft', methods=['POST'])
def save_draft():
    # in the next step we’ll persist to gil_reports/editor_json.
    # for now, just accept payload and return success.
    _ = request.get_json(silent=True) or {}
    return jsonify({'status': 'ok'})

# ---- STUB: Preview — returns a placeholder PDF stream (replace later)
@reports_ui_bp.route('/preview', methods=['POST'])
def preview():
    # for now we return a 1-page blank-ish PDF with a title.
    # later: render HTML -> PDF using WeasyPrint/wkhtmltopdf + actual data.
    from reportlab.pdfgen import canvas  # already bundled in many envs; if not, swap to any tiny static PDF file
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(80, 780, "דו״ח מעקב — תצוגה מקדימה (Placeholder)")
    c.setFont("Helvetica", 11)
    c.drawString(80, 750, "נמלא בתוכן אמיתי בשלב 2.")
    c.showPage()
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=False, download_name='preview.pdf')

# ---- STUB: Final actions: version/save/send — just echoes success for now
@reports_ui_bp.route('/finalize', methods=['POST'])
def finalize():
    action = request.form.get('action')  # 'version' | 'save_to_dropbox' | 'send_to_insurer'
    # next step: implement real behavior per action
    return jsonify({'status':'ok', 'action': action, 'message': 'Stubbed OK'})
