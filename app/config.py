import os
import json

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://dor_pi:T0m3r!970S@172.234.160.57/dor_pi'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads/insured_photos'

    # Path to the clinics JSON file
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CLINICS_FILE = os.path.join(BASE_DIR, "clinics.json")

    @classmethod
    def load_clinics(cls):
        """Load clinics from the JSON file."""
        with open(cls.CLINICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

# Load clinics list after class definition is complete
Config.CLINICS_LIST = Config.load_clinics()





