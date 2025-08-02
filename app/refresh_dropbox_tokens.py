import dropbox

APP_KEY = "078cfveyiewj0ay"
APP_SECRET = "9h1uxluft07vap1"

auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(
    APP_KEY, APP_SECRET, token_access_type='offline'
)

authorize_url = auth_flow.start()
print("🔗 Visit this URL and authorize the app:\n", authorize_url)

auth_code = input("🔐 Paste the authorization code here: ").strip()
oauth_result = auth_flow.finish(auth_code)

print("\n✅ SUCCESS")
print("Access Token:", oauth_result.access_token)
print("Refresh Token:", oauth_result.refresh_token)
print("Account ID:", oauth_result.account_id)
