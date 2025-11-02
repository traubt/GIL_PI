import os
import json

class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://dor_pi:T0m3r!970S@172.234.160.57/dor_pi'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads/insured_photos'

    # Where report-related media (e.g., uploaded photos) is stored
    REPORT_MEDIA_DIR = "/var/app/uploads/reports"

    # --- Paths / files inside the app package ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../app
    CLINICS_FILE = os.path.join(BASE_DIR, "clinics.json")

    # --- DOCX templates & output ---
    # You can override these with environment variables:
    #   DOCX_TEMPLATES_DIR, DOCX_OUTPUT_DIR
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

# Ensure output directory exists (harmless if already there)
os.makedirs(Config.DOCX_OUTPUT_DIR, exist_ok=True)






