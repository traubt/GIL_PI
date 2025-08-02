import dropbox

DROPBOX_REFRESH_TOKEN = 'YjUT_g2Om4wAAAAAAAAAATogIV7e_NrU4uRcaIfo2WUOxiTwfg-brX6-3u5M991-'
DROPBOX_APP_KEY = '078cfveyiewj0ay'
DROPBOX_APP_SECRET = '9h1uxluft07vap1'

# Initialize Dropbox client
dbx = dropbox.Dropbox(
    oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
    app_key=DROPBOX_APP_KEY,
    app_secret=DROPBOX_APP_SECRET
)

try:
    # ✅ Create the folder
    folder_path = '/TOMER_TEST'  # Root-level folder
    dbx.files_create_folder_v2(folder_path)
    print(f"✅ Folder '{folder_path}' created successfully.")

    # 🔍 List root folder to confirm
    print("\n📁 Root folder contents:")
    result = dbx.files_list_folder("")
    for entry in result.entries:
        print("📄", entry.name)

except dropbox.exceptions.AuthError as e:
    print("❌ Auth failed:", e)
except dropbox.exceptions.ApiError as e:
    if e.error.is_path() and e.error.get_path().is_conflict():
        print(f"⚠️ Folder '{folder_path}' already exists.")
    else:
        print("❌ API error:", e)
