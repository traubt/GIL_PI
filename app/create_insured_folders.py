import dropbox
import pymysql
from sqlalchemy import create_engine, text

# Dropbox setup
DROPBOX_REFRESH_TOKEN = 'YjUT_g2Om4wAAAAAAAAAATogIV7e_NrU4uRcaIfo2WUOxiTwfg-brX6-3u5M991-'
DROPBOX_APP_KEY = '078cfveyiewj0ay'
DROPBOX_APP_SECRET = '9h1uxluft07vap1'

dbx = dropbox.Dropbox(
    oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
    app_key=DROPBOX_APP_KEY,
    app_secret=DROPBOX_APP_SECRET
)

# === MySQL Connection ===
engine = create_engine("mysql+pymysql://dor_pi:T0m3r!970@172.234.160.57/dor_pi")

# === Folder path builder ===
def build_folder_path(insurance, claim_type, last_name, first_name, id_number, claim_number):
    base_path = f"/360/ביטוח/{insurance}/{claim_type}"
    full_name = f"{last_name} {first_name}"

    if insurance == 'מנורה':
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    elif insurance == 'הפניקס':
        folder_name = f"{full_name} - {claim_number}"
    elif insurance == 'שלמה' and claim_type == 'אכע':
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    elif insurance == 'איילון' and claim_type == 'אכע':
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    else:
        return None  # skip unsupported combo

    return f"{base_path}/{folder_name}"



# === Process insured list ===
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT last_name, first_name, insurance, claim_type, id_number, claim_number
        FROM gil_insured
        WHERE last_name IS NOT NULL AND first_name IS NOT NULL
          AND insurance IS NOT NULL AND claim_type IS NOT NULL
          AND id_number IS NOT NULL AND claim_number IS NOT NULL
    """)).fetchall()

    for row in result:
        last_name, first_name, insurance, claim_type, id_number, claim_number = row
        folder_path = build_folder_path(insurance, claim_type, last_name, first_name, id_number, claim_number)

        if folder_path:
            print("→", folder_path)
            try:
                dbx.files_create_folder_v2(folder_path)
                print(f"✅ Created: {folder_path}")
            except dropbox.exceptions.ApiError as e:
                if isinstance(e.error, dropbox.files.CreateFolderError) and e.error.get_path().is_conflict():
                    print(f"⚠️ Already exists: {folder_path}")
                else:
                    print(f"❌ Error for {folder_path}: {e}")