import os
import json
import platform
import shutil
from pathlib import Path


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://dor_pi:T0m3r!970S@172.234.160.57/dor_pi'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Project/app base
    BASE_DIR = Path(__file__).resolve().parent  # .../app

    # Where user-uploaded insured photos live (relative to project root by default)
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "insured_photos"

    # LibreOffice binary (env override -> auto-detect -> OS-specific default)
    LIBREOFFICE_BIN = (
        os.environ.get('LIBREOFFICE_BIN')
        or shutil.which('soffice')
        or shutil.which('libreoffice')
        or (
            r"C:\Program Files\LibreOffice\program\soffice.com"
            if platform.system() == "Windows" else "/usr/bin/soffice"
        )
    )

    # Where report-related media (e.g., uploaded photos used inside reports) is stored
    # Use env var if set; on Linux default to /var/app/uploads/reports; on Windows default to project/uploads/reports
    _default_media_dir = (
        "/var/app/uploads/reports"
        if platform.system() != "Windows"
        else os.path.abspath(os.path.join(BASE_DIR, "..", "uploads", "reports"))
    )
    REPORT_MEDIA_DIR = os.environ.get("REPORT_MEDIA_DIR", _default_media_dir)

    # --- Paths / files inside the app package ---
    CLINICS_FILE = os.path.join(BASE_DIR, "clinics.json")

    # --- DOCX templates & output ---
    DOCX_TEMPLATES_DIR = os.environ.get(
        "DOCX_TEMPLATES_DIR",
        os.path.join(BASE_DIR, "docx_templates")            # app/docx_templates
    )

    DOCX_OUTPUT_DIR = os.environ.get(
        "DOCX_OUTPUT_DIR",
        os.path.abspath(os.path.join(BASE_DIR, "..", "generated_reports"))  # project/generated_reports
    )

    @classmethod
    def load_clinics(cls):
        """Load clinics from the JSON file."""
        with open(cls.CLINICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


# Load clinics list after class definition is complete
Config.CLINICS_LIST = Config.load_clinics()

# --- Ensure important directories exist (safe if already there) ---
os.makedirs(Config.DOCX_OUTPUT_DIR, exist_ok=True)
os.makedirs(Config.REPORT_MEDIA_DIR, exist_ok=True)

# If UPLOAD_FOLDER is relative, resolve it relative to project root and ensure it exists
_upload_path = Path(Config.UPLOAD_FOLDER)
if not _upload_path.is_absolute():
    _upload_path = Path(Config.BASE_DIR).parent / _upload_path
os.makedirs(_upload_path, exist_ok=True)
