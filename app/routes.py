from flask import Blueprint,  flash
from .models import *
from .db_queries import *
from datetime import  timezone
from flask import Flask
from sqlalchemy import  desc
from flask import session
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import openai
import re
from app.tables_for_openAI import DATABASE_SCHEMA
from flask import redirect, url_for, current_app
import os
from flask import render_template, request, jsonify
from app import db
from app.models import GilInsured
from datetime import datetime, timedelta
from .dropbox_util import get_dbx

from decimal import Decimal, InvalidOperation


from sqlalchemy import text



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
main = Blueprint('main', __name__)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SENDER_EMAIL = 'algott.team@gmail.com'
SENDER_PASSWORD = 'xiyaxiztcekbkvtu'

DB_CONFIG = {
    'host': '176.58.117.107',
    'user': 'tasteofc_wp268',
    'password': ']44p7214)S',
    'database': 'tasteofc_wp268',
    'cursorclass': pymysql.cursors.DictCursor  # Return rows as dictionaries
}

import dropbox
from dropbox.exceptions import ApiError
from werkzeug.utils import secure_filename

# Dropbox setup
DROPBOX_REFRESH_TOKEN = 'YjUT_g2Om4wAAAAAAAAAATogIV7e_NrU4uRcaIfo2WUOxiTwfg-brX6-3u5M991-'
DROPBOX_APP_KEY = '078cfveyiewj0ay'
DROPBOX_APP_SECRET = '9h1uxluft07vap1'

dbx = dropbox.Dropbox(
    oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
    app_key=DROPBOX_APP_KEY,
    app_secret=DROPBOX_APP_SECRET
)

def build_dropbox_folder_path(insurance, claim_type, last_name, first_name, id_number, claim_number):
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
        return None

    return f"{base_path}/{folder_name}"

def _extract_taken_at_from_exif_bytes(data: bytes):
    """
    Returns datetime or None.
    Safe bytes-based EXIF read (works even after file.read()).
    """
    try:
        from PIL import Image
        import io
        from datetime import datetime

        img = Image.open(io.BytesIO(data))
        exif = getattr(img, "_getexif", None)
        if not exif:
            return None

        # 36867 = DateTimeOriginal, 306 = DateTime
        dt = exif.get(36867) or exif.get(306)
        if not dt:
            return None

        # EXIF format: "YYYY:MM:DD HH:MM:SS"
        return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def sync_insured_to_dropbox(insured, photo_path=None):
    folder_path = build_dropbox_folder_path(
        insured.insurance, insured.claim_type,
        insured.last_name, insured.first_name,
        insured.id_number, insured.claim_number
    )
    if not folder_path:
        return

    try:
        dbx.files_create_folder_v2(folder_path)
    except ApiError as e:
        if not (e.error.is_path() and e.error.get_path().is_conflict()):
            raise

    # Upload photo if path is provided
    if photo_path:
        dropbox_path = f"{folder_path}/{secure_filename(insured.photo)}"
        with open(photo_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

# Function to send email
def send_email(recipients, subject, body):
    try:
        # Create the message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ', '.join(recipients)  # Send to multiple recipients
        msg['Subject'] = subject

        # Add the email body
        msg.attach(MIMEText(body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())

        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

def is_safe_sql(sql):
    """
    Check if a given SQL query is safe for execution (only SELECT allowed).
    """
    forbidden_keywords = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER']
    for keyword in forbidden_keywords:
        if re.search(r'\b' + keyword + r'\b', sql, re.IGNORECASE):
            return False
    return sql.strip().upper().startswith('SELECT')

# ===============================
# Helper Function: Execute Safe SQL
# ===============================
def execute_sql(sql):
    """
    Executes a safe SELECT SQL query and returns columns and rows.
    """
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]  # Get column names
            rows = cursor.fetchall()  # Fetch all results
        return columns, rows
    finally:
        connection.close()

def load_clinics():
    """Read the clinics list from clinics.json."""
    with open(current_app.config['CLINICS_FILE'], "r", encoding="utf-8") as f:
        return json.load(f)

def append_clinic(new_clinic):
    """Append a clinic to clinics.json if not already there."""
    clinics = load_clinics()
    if new_clinic not in clinics:
        clinics.append(new_clinic)
        with open(current_app.config['CLINICS_FILE'], "w", encoding="utf-8") as f:
            json.dump(clinics, f, ensure_ascii=False, indent=2)

def format_time(value):
    """Convert MySQL TIME (timedelta) to HH:MM string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:5]  # already a string "HH:MM:SS"
    if isinstance(value, datetime.timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    return str(value)

def normalize_date(value):
    """Return ISO date string YYYY-MM-DD or ''."""
    if not value:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).split(" ")[0]  # fallback

def normalize_time(value):
    """Return HH:MM string or ''."""
    if not value:
        return ""
    if isinstance(value, str):
        return value[:5]  # "HH:MM"
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    try:
        # Handle timedelta from MySQL
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    except Exception:
        return str(value)

from datetime import datetime, time

def parse_time(value):
    """Convert string like '14:30' or '14:30:00' to datetime.time."""
    if not value:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except ValueError:
            try:
                return datetime.strptime(value.strip(), "%H:%M:%S").time()
            except ValueError:
                return None
    return None

# =========================
# Tracking Reports Helpers
# =========================

def parse_date_flexible(value: str):
    """
    Accepts:
      - "YYYY-MM-DD"
      - "DD/MM/YYYY"
    Returns: datetime.date | None
    """
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def get_current_investigator_row():
    """
    Returns GilInvestigator row for the logged-in user (role Investigator).
    Uses the same matching logic you already use in /investigators route.
    """
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    if not user:
        return None

    inv_row = GilInvestigator.query.filter_by(user_id=user.get("id")).first()
    if not inv_row:
        full_name = f"{user.get('first_name','').strip()} {user.get('last_name','').strip()}".strip()
        inv_row = GilInvestigator.query.filter_by(full_name=full_name).first()

    return inv_row


def user_is_admin_or_manager(user: dict) -> bool:
    # adjust if you later add MANAGER role etc.
    role = (user.get("role") or "").strip()
    return role in ("ADMIN", "Admin", "Manager", "SUPERADMIN")


def require_case_access_or_403(insured_id: int, ref_number: str):
    """
    Investigator can only access insured cases assigned to him via gil_investigator_case.active=1.
    Admin/Manager can access everything.
    Returns: (allowed: bool, inv_row: GilInvestigator|None, user: dict)
    """
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    if not user:
        return False, None, user

    if user_is_admin_or_manager(user):
        return True, None, user

    # investigators only
    if user.get("role") != "Investigator":
        return False, None, user

    inv_row = get_current_investigator_row()
    if not inv_row:
        return False, None, user

    link = GilInvestigatorCase.query.filter_by(
        insured_id=insured_id,
        investigator_id=inv_row.id,
        active=True
    ).first()

    return bool(link), inv_row, user



@main.route('/send_email', methods=['POST'])
def handle_send_email():
    try:
        # Get data from the client (list of recipients, subject, and body)
        data = request.get_json()
        recipients = data.get('recipients', [])
        subject = data.get('subject', '')
        body = data.get('body', '')

        # Validate input data
        if not recipients or not subject or not body:
            return jsonify({"error": "Missing required fields"}), 400

        # Call the function to send the email
        send_email(recipients, subject, body)

        return jsonify({"message": "Email sent successfully!"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

@main.route('/')
def login():
    return render_template('login.html')

@main.route('/ChatGPT')
def ChatGPT():
    user_data = session.get('user')
    roles = TocRole.query.all()
    shops = TOC_SHOPS.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    list_of_shops = [shop.blName for shop in shops]

    if user_data:
        user = json.loads(user_data)
        return render_template('openAI.html', user=user, roles=roles_list, shops=list_of_shops)  # Pass as JSON
    else:
        return redirect(url_for('main.login'))


@main.route('/index')
def index():

    user_data = session.get('user')
    roles = TocRole.query.all()
    shops = TOC_SHOPS.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    list_of_shops = [shop.blName for shop in shops]

    if user_data:
        user = json.loads(user_data)
        return render_template('index.html', user=user, roles=roles_list, shops=list_of_shops)  # Pass as JSON
    else:
        return redirect(url_for('main.login'))

@main.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if not user or user.password != password:
        flash('User/password invalid')
        return redirect(url_for('main.login'))

    # Serialize user object
    user_data = {
        'id': user.id,
        'username': user.username,
        'password': user.password,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'shop': user.shop,
        'role': user.role
    }
    session['user'] = json.dumps(user_data)

    # Save to the session shop data
    shop = TOC_SHOPS.query.filter_by(blName=user.shop).first()
    if shop:
        shop_data = {
            'name': shop.blName,
            'code': shop.store,
            'customer': shop.customer
        }
        session['shop'] = json.dumps(shop_data)

    # Log user activity
    new_activity = TOCUserActivity(
        user=user.username,
        shop=shop.customer if shop else None,
        activity="User login"
    )
    db.session.add(new_activity)
    db.session.commit()

    # Redirect based on role
    if user.role == "Investigator":
        return redirect(url_for("main.investigator_dashboard"))
    else:
        return redirect(url_for('main.admin_insured'))

@main.route('/welcome/<username>')
def welcome(username):
    return f'Welcome {username}'

@main.route('/register')
def register():
    shops = TOC_SHOPS.query.all()
    # Fetch all roles from the TocRole table
    roles = TocRole.query.all()
    role_list = [role.role for role in roles]  # Extract roles as a list
    return render_template('register.html', shops=shops, roles = role_list)

@main.route('/faq')
def faq():
    return render_template('pages-faq.html')

@main.route('/template')
def template():
    return render_template('pages-blank.html')

@main.route('/admin_users')
def admin_users():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'user_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/admin_investigators')
def admin_investigators():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'investigators_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/admin_logs')
def admin_logs():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'log_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/user_activity')
def user_activity():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'user_activity.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/api/get_users')
def get_users():
    users = User.query.all()
    users_list = [{
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'shop': user.shop,
        'password': user.password,
        'role': user.role,
    } for user in users]
    return jsonify(users_list)

@main.route('/api/get_logs')
def get_logs():
    logs = TocSalesLog.query.order_by(desc(TocSalesLog.run_id)).limit(50).all()
    TocSalesLogs_list = [{
        'id': log.run_id,
        'start_date': log.start_date,
        'end_date': log.end_date,
        'search_from': log.search_from,
        'num_of_sales': log.num_of_sales,
        'source': log.source,
        'comment': log.comment,
    } for log in logs]
    return jsonify(TocSalesLogs_list)

@main.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        # Retrieve the user object by user_id
        user = User.query.get(user_id)

        if user:
            # Delete the user if found
            db.session.delete(user)
            db.session.commit()
            return jsonify({"message": f"User {user_id} deleted successfully."}), 200
        else:
            # If user not found, return an error
            return jsonify({"error": f"User {user_id} not found."}), 404

    except Exception as e:
        # Handle any exceptions that occur during deletion
        print(f"Error occurred while deleting user: {e}")
        return jsonify({"error": "An error occurred while deleting the user."}), 500

@main.route('/api/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        # Get the user by ID
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update fields with form data
        user.email = request.form.get('email')
        user.password = request.form.get('password')
        user.role = request.form.get('role')
        user.shop = request.form.get('shop')

        # Commit changes to the database
        db.session.commit()
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": "An error occurred while updating the user"}), 500

@main.route('/api/update_password/<string:password>', methods=['PUT'])
def update_password(password):
    try:
        # Get the user by ID
        user_data = session.get('user')
        user = User.query.get(json.loads(user_data)["id"])
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update fields with form data
        user.password = password

        # Commit changes to the database
        db.session.commit()
        return jsonify({"message": "User password updated successfully"}), 200
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": "An error occurred while updating the user"}), 500

@main.route('/user_profile')
def user_profile():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('users-profile.html', user=user, shop=shop, roles=roles_list)

@main.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    shop = request.form.get('shop')
    role = request.form.get('role')

    user = User.query.filter_by(username=username).first()

    if user:
        flash('Username already exists')
        return redirect(url_for('main.register'))


    if not username or not password or not first_name or not last_name or not email or '@' not in email:
        flash('Please fill out all fields correctly')
        return redirect(url_for('main.register'))

    new_user = User(username=username, password=password, first_name=first_name, last_name=last_name, email=email, shop=shop, role=role)
    db.session.add(new_user)
    db.session.commit()

    # Create a new TOCUserActivity record
    new_activity = TOCUserActivity(
        user=username,  # Assuming the username is stored in user["username"]
        shop=shop,  # Assuming the shop name is stored in shop["customer"]
        activity="New registration"
    )

    # Add the record to the session and commit to the database
    db.session.add(new_activity)
    db.session.commit()

    # flash('User registered successfully')
    return redirect(url_for('main.admin_users'))

@main.route('/save_csv', methods=['POST'])
def save_csv():
    data = request.get_json()
    csv_data = data['csv_data']
    shop_data = json.loads(session.get('shop'))
    shop = shop_data['name']
    shop_code = shop_data['customer']

    # Create directory if it doesn't exist
    directory = os.path.join('app/static', shop_code)
    print(f"save file to directory: {directory}")
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Save CSV file with current store and date as filename
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    date_str = shop_code+"_"+date_str
    file_path = os.path.join(directory, f'{date_str}.csv')
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(csv_data)

    return jsonify({'message': 'CSV saved successfully', 'file_path': file_path})

@main.route('/create_message', methods=['POST'])
def create_message():
    data = request.get_json()

    new_message = TocMessages(
        msg_date=data.get('msg_date'),
        msg_from=data.get('msg_from'),
        msg_to=data.get('msg_to'),
        msg_subject=data.get('msg_subject'),
        msg_body=data.get('msg_body'),
        msg_status=data.get('msg_status')
    )

    db.session.add(new_message)
    db.session.commit()

    return jsonify({'message': 'Message created successfully!', 'msg_id': new_message.msg_id}), 201

@main.route('/create_notification', methods=['POST'])
def create_notification():
    data = request.get_json()

    new_notification = TocNotification(
        not_date=data.get('not_date'),
        not_address=data.get('not_address'),
        not_subject=data.get('not_subject'),
        not_body=data.get('not_body'),
        not_status=data.get('not_status')
    )

    db.session.add(new_notification)
    db.session.commit()

    return jsonify({'message': 'Notification created successfully!', 'not_id': new_notification.not_id}), 201

@main.route('/get_all_notifications', methods=['GET'])
def get_all_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    notifications = TocNotification.query.filter_by(not_address=shop_name).all()
    notifications_list = [
        {
            'not_date': notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]
    return jsonify(notifications_list)

@main.route('/get_unread_notifications', methods=['GET'])
def get_unread_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    notifications = TocNotification.query.filter_by(not_address=shop_name, not_status="unread").all()
    notifications_list = [
        {
            'not_date' : notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]
    return jsonify(notifications_list)

@main.route('/api/toc_shops', methods=['GET'])
def get_toc_shops():
    shops = TOC_SHOPS.query.all()  # Query all rows
    shops_data = [
        {
            "blName": shop.blName,
            "blId": shop.blId,
            "country": shop.country,
            "timezone": shop.timezone,
            "store": shop.store,
            "customer": shop.customer,
            "mt_shop_name": shop.mt_shop_name,
        }
        for shop in shops
    ]
    return jsonify(shops_data)

@main.route('/get_and_mark_notifications', methods=['GET'])
def get_and_mark_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Retrieve unread notifications
    notifications = TocNotification.query.filter_by(not_address=shop_name, not_status="unread").all()

    # Mark notifications as read
    for notification in notifications:
        notification.not_status = "read"

    # Commit the changes to the database
    db.session.commit()

    # Prepare the list of notifications to return
    notifications_list = [
        {
            'not_date': notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]

    return jsonify(notifications_list)

@main.route('/log_user_activity', methods=['POST'])
def log_user_activity():
    try:
        # Retrieve user and shop data from the session
        user_data = session.get('user')
        user = json.loads(user_data)
        shop_data = session.get('shop')
        shop = json.loads(shop_data)

        # Get the activity description from the client
        activity = request.json.get('activity')
        if not activity:
            return {"error": "Activity description is required"}, 400

        # Create a new TOCUserActivity record
        new_activity = TOCUserActivity(
            user=user["username"],  # Assuming the username is stored in user["username"]
            shop=shop["customer"],  # Assuming the shop name is stored in shop["customer"]
            activity=activity
        )

        # Add the record to the session and commit to the database
        db.session.add(new_activity)
        db.session.commit()

        return {"message": "User activity logged successfully"}, 200

    except Exception as e:
        print(f"Error logging user activity: {e}")
        return {"error": "Failed to log user activity"}, 500

#####################################  Reports Section

@main.route('/get_user_activity', methods=['GET'])
def get_user_activity():

    # Simulated function to get columns and rows
    column_names, data = get_user_activities()  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route("/update_user_login", methods=["POST"])
def update_user_login():
    user_data = session.get("user")
    if not user_data:
        # Not logged in (or session not set yet) -> don't crash
        return jsonify({"success": False, "error": "Not logged in"}), 401

    try:
        user_session = json.loads(user_data)
    except Exception:
        return jsonify({"success": False, "error": "Invalid session user"}), 400

    user_id = user_session.get("id")
    if not user_id:
        return jsonify({"success": False, "error": "Missing user id in session"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json(silent=True) or {}

    try:
        user.last_login_date = datetime.now(timezone.utc)
        user.ip = data.get("ip")
        user.city = data.get("city")
        user.county = data.get("county")
        user.loc = data.get("loc")
        user.postal = data.get("postal")
        user.region = data.get("region")
        user.timezone = data.get("timezone")
        user.country_code = data.get("country_code")
        user.country_calling_code = data.get("country_calling_code")

        db.session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        print(f"update_user_login failed: {e}")
        return jsonify({"success": False, "error": "Failed to update login"}), 500


#########################  OPENAI section  #####################
@main.route('/api/ask_business', methods=['POST'])
def ask_business():
    try:

        openai.api_key = current_app.config["OPENAI_KEY"]
        # Get the user question and username from frontend
        data = request.get_json()
        user_question = data.get('question')
        user_name = data.get('username')  # NEW: capture username

        user_data = json.loads(session.get('user'))
        username = user_data['username']
        shop_name = user_data['shop']

        if not user_question or not username:
            return jsonify({'error': 'Username and question are required.'}), 400

        # Build the system prompt
        system_prompt = f"""
You are a business data analyst working on an ERP system called "360".
ONLY respond with a clean MySQL SELECT query based on the database schema provided below.

Database Schema:
{DATABASE_SCHEMA}

Strict Rules:
- Only generate SELECT queries.
- Never modify, delete, insert, or drop anything.
- Never use ALTER, DELETE, UPDATE, DROP, INSERT commands.
- Always use MySQL syntax.
- Limit the results to 100 rows unless user explicitly says otherwise.
- **If more than one table is used, always prefix field names with the table name.**
- Reply ONLY with the SQL inside triple backticks (```) and nothing else.

User's Question:
"{user_question}"

Example format you must use:
```sql
SELECT * FROM toc_ls_sales LIMIT 10;
"""
        # Send prompt to OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # or "gpt-4-turbo" if you prefer
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0
        )

        # Extract SQL from OpenAI response
        chat_response = response['choices'][0]['message']['content']
        match = re.search(r'```sql\s*(.*?)\s*```', chat_response, re.DOTALL)
        if not match:
            return jsonify({'error': 'Failed to extract SQL from AI response.'}), 500

        generated_sql = match.group(1).strip()

        # Validate SQL (only SELECT allowed)
        if not is_safe_sql(generated_sql):
            return jsonify({'error': 'Generated SQL is unsafe or invalid.'}), 400

        # Execute the safe SQL query
        columns, rows = execute_sql(generated_sql)

        # Format the result into HTML Bootstrap table
        table_html = '<table class="table table-striped table-bordered table-hover table-sm">'
        table_html += '<thead><tr>' + ''.join(f'<th>{col}</th>' for col in columns) + '</tr></thead><tbody>'
        for row in rows:
            table_html += '<tr>' + ''.join(f'<td>{row[col]}</td>' for col in columns) + '</tr>'
        table_html += '</tbody></table>'

        # NEW: Save user query into toc_openai
        from app.models import TOCOpenAI  # Import your model
        from app import db  # Import your db object

        new_record = TOCOpenAI(
            username=username,
            name=user_name,        # Optional until you provide better info
            shop_name=shop_name,
            user_query=user_question
        )
        db.session.add(new_record)
        db.session.commit()

        # Return SQL + results to frontend
        return jsonify({
            'generated_sql': generated_sql,
            'result_html': table_html
        })

    except Exception as e:
        logger.exception("💥 Error in /api/ask_business:")  # DEBUG print
        return jsonify({'error': str(e)}), 500

############################## END OPENAI section######################################
############################## GIL CUSTOMIZATION ######################################

@main.route('/admin_insured')
def admin_insured():

    # session context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    investigators = GilInvestigator.query.order_by(GilInvestigator.full_name.asc()).all()
    koopa_list = GilKoopa.query.order_by(GilKoopa.koopa_name.asc()).all()
    investigators_json = [
        {"id": inv.id, "full_name": inv.full_name, "user_id": inv.user_id}
        for inv in investigators
    ]

    # role list
    roles = db.session.query(TocRole).all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    # base query - exclude status "הושלמה"
    query = db.session.query(GilInsured).filter(GilInsured.status != "הושלמה")

    # filters
    insurance = request.args.get('insurance')
    status = request.args.get('status')
    name = request.args.get('name')

    if insurance:
        query = query.filter(GilInsured.insurance == insurance)
    if status:
        query = query.filter(GilInsured.status == status)
    if name:
        query = query.filter(
            (GilInsured.first_name.ilike(f"%{name}%")) |
            (GilInsured.last_name.ilike(f"%{name}%"))
        )

    insured_list = query.order_by(GilInsured.received_date.desc()).all()

    return render_template(
        'insured_admin.html',
        user=user,
        shop=shop,
        roles=roles_list,
        insured_list=insured_list,
        investigators=investigators,
        investigators_json=investigators_json,  # use only for JS logging
        koopa_list=koopa_list
    )

@main.route('/insured/create', methods=['GET', 'POST'])
def create_insured():
    # Fetch clinics and koopa from the database
    clinics = GilClinics.query.all()
    koopa = GilKoopa.query.all()

    user_data = session.get('user')
    user = json.loads(user_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    investigators = GilInvestigator.query.order_by(GilInvestigator.full_name).all()

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    birth_date_str = request.form.get('birth_date')

    if request.method == 'POST':
        try:
            investigator_list = request.form.getlist('investigator')
            investigator_str = '*'.join(investigator_list) if investigator_list else None

            # Handle clinic/koopa new entry
            clinic = request.form.get('clinic')
            if clinic == '__new__':
                clinic_name = request.form.get('new_clinic', '').strip()
                if clinic_name:
                    # Save to database
                    new_clinic = GilClinics(clinic_name=clinic_name)
                    db.session.add(new_clinic)
                    db.session.commit()
                    clinic = clinic_name  # Set the new clinic as the selected one

            koopa = request.form.get('koopa')
            if koopa == '__new__':
                koopa_name = request.form.get('new_koopa', '').strip()
                if koopa_name:
                    # Save to database
                    new_koopa = GilKoopa(koopa_name=koopa_name)
                    db.session.add(new_koopa)
                    db.session.commit()
                    koopa = koopa_name  # Set the new koopa as the selected one

            insured = GilInsured(
                ref_number=request.form.get('ref_number'),
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                id_number=request.form.get('id_number'),
                birth_date=birth_date_str if birth_date_str else None,
                father_name=request.form.get('father_name'),
                city=request.form.get('city'),
                address=request.form.get('address'),
                gender=request.form.get('gender'),
                phone=request.form.get('phone'),
                koopa=koopa,
                clinic=clinic,
                insurance=request.form.get('insurance'),
                claim_type=request.form.get('claim_type'),
                claim_number=request.form.get('claim_number'),
                investigator=investigator_str,
                notes=request.form.get('notes'),
                received_date=request.form.get('received_date') or None,
                parkinson_ind=1 if request.form.get('parkinson_ind') == 'on' else 0
            )

            # Handle photo upload
            photo = request.files.get('photo')
            if photo and photo.filename:
                ext = photo.filename.rsplit('.', 1)[-1].lower()
                if ext in {'jpg', 'jpeg', 'png'}:
                    os.makedirs(upload_folder, exist_ok=True)
                    photo_filename = f"{insured.id_number}_{secure_filename(photo.filename)}"
                    photo.save(os.path.join(upload_folder, photo_filename))
                    insured.photo = photo_filename
                else:
                    return jsonify({'status': 'error', 'message': 'רק קבצי JPG או PNG מותרים'}), 400

            db.session.add(insured)
            db.session.commit()

            # Sync to Dropbox
            photo_path = os.path.join(upload_folder, insured.photo) if photo and insured.photo else None
            sync_insured_to_dropbox(insured, photo_path=photo_path)

            return jsonify({
                "status": "success",
                "message": "המבוטח נוצר בהצלחה",
                "insured_id": insured.id
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating insured: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "שגיאה ביצירת מבוטח"
            }), 500

    return render_template('insured.html',
                           insured=None,
                           investigators=investigators,
                           user=user,
                           roles=roles_list,
                           clinics=clinics,
                           koopa=koopa)

@main.route('/insured/<int:id>/edit', methods=['GET', 'POST'])
def edit_insured(id):
    # Fetch clinics and koopa from the database
    clinics = GilClinics.query.all()
    koopa = GilKoopa.query.all()

    insured = GilInsured.query.get_or_404(id)

    user_data = session.get('user')
    user = json.loads(user_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    investigators = GilInvestigator.query.order_by(GilInvestigator.full_name).all()

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    birth_date_str = request.form.get('birth_date')

    if request.method == 'POST':
        try:
            investigator_list = request.form.getlist('investigator')
            investigator_str = '*'.join(investigator_list) if investigator_list else None

            # Handle clinic/koopa new entry
            clinic = request.form.get('clinic')
            if clinic == '__new__':
                clinic_name = request.form.get('new_clinic', '').strip()
                if clinic_name:
                    # Save to database
                    new_clinic = GilClinics(clinic_name=clinic_name)
                    db.session.add(new_clinic)
                    db.session.commit()
                    clinic = clinic_name  # Set the new clinic as the selected one

            koopa = request.form.get('koopa')
            if koopa == '__new__':
                koopa_name = request.form.get('new_koopa', '').strip()
                if koopa_name:
                    # Save to database
                    new_koopa = GilKoopa(koopa_name=koopa_name)
                    db.session.add(new_koopa)
                    db.session.commit()
                    koopa = koopa_name  # Set the new koopa as the selected one

            # Update insured details
            insured.ref_number = request.form.get('ref_number')
            insured.first_name = request.form.get('first_name')
            insured.last_name = request.form.get('last_name')
            insured.id_number = request.form.get('id_number')
            insured.birth_date = birth_date_str if birth_date_str else None
            insured.father_name = request.form.get('father_name')
            insured.city = request.form.get('city')
            insured.address = request.form.get('address')
            insured.gender = request.form.get('gender')
            insured.phone = request.form.get('phone')
            insured.koopa = koopa
            insured.clinic = clinic
            insured.insurance = request.form.get('insurance')
            insured.claim_type = request.form.get('claim_type')
            insured.claim_number = request.form.get('claim_number')
            insured.investigator = investigator_str
            insured.notes = request.form.get('notes')
            insured.received_date = request.form.get('received_date') or None
            insured.status = request.form.get('status')
            insured.recurring_appointments = request.form.get('recurring_appointments')
            insured.parkinson_ind = 1 if request.form.get('parkinson_ind') == 'on' else 0

            # Handle photo upload
            photo = request.files.get('photo')
            if photo and photo.filename:
                ext = photo.filename.rsplit('.', 1)[-1].lower()
                if ext in {'jpg', 'jpeg', 'png'}:
                    os.makedirs(upload_folder, exist_ok=True)
                    photo_filename = f"{insured.id_number}_{secure_filename(photo.filename)}"
                    photo.save(os.path.join(upload_folder, photo_filename))
                    insured.photo = photo_filename
                else:
                    return jsonify({'status': 'error', 'message': 'רק קבצי JPG או PNG מותרים'}), 400

            db.session.commit()

            # Sync Dropbox if ID or claim number changed, or photo updated
            id_or_claim_changed = insured.id_number != insured.id_number or insured.claim_number != insured.claim_number
            if id_or_claim_changed or photo:
                photo_path = os.path.join(upload_folder, insured.photo) if insured.photo else None
                sync_insured_to_dropbox(insured, photo_path=photo_path)

            return jsonify({
                "status": "success",
                "message": "פרטי המבוטח עודכנו בהצלחה",
                "insured_id": insured.id
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating insured: {str(e)}")
            return jsonify({'status': 'error', 'message': 'שגיאה בעדכון פרטי המבוטח'}), 500

    return render_template('insured.html',
                           insured=insured,
                           investigators=investigators,
                           user=user,
                           roles=roles_list,
                           clinics=clinics,
                           koopa=koopa)

@main.route('/insured/assign_investigator', methods=['POST'])
def assign_investigator():
    try:
        insured_id = request.form.get('insured_id', type=int)
        if not insured_id:
            return jsonify({'status': 'error', 'message': 'insured_id חסר'}), 400

        # Accept either "investigators" or "investigators[]" from jQuery
        selected = request.form.getlist('investigators') or request.form.getlist('investigators[]')
        selected = [s.strip() for s in selected if s and s.strip()]

        insured = GilInsured.query.get_or_404(insured_id)

        # Resolve investigator IDs from names
        inv_ids = []
        for sel in selected:
            inv = GilInvestigator.query.filter_by(full_name=sel).first()
            if inv:
                inv_ids.append(inv.id)

        # --- Update legacy field (as today) ---
        insured.investigator = '*'.join(selected) if selected else None

        # --- Update relational table ---
        existing_links = {link.investigator_id: link for link in insured.investigator_links if link.active}

        # Add or reactivate selected
        for inv_id in inv_ids:
            link = existing_links.get(inv_id)
            if link:
                link.active = True
            else:
                db.session.add(GilInvestigatorCase(
                    insured_id=insured.id,
                    investigator_id=inv_id,
                    assigned_by=json.loads(session.get('user'))["id"] if session.get('user') else None
                ))

        # Deactivate removed
        for inv_id, link in existing_links.items():
            if inv_id not in inv_ids:
                link.active = False

        db.session.commit()

        return jsonify({'status': 'success', 'investigator': insured.investigator or ''})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'assign_investigator error: {e}')
        return jsonify({'status': 'error', 'message': 'שגיאה בעדכון חוקר'}), 500

def load_clinics():
    """Read clinics list from clinics.json, return [] if file is empty/missing."""
    path = current_app.config['CLINICS_FILE']
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

def append_clinic(name: str) -> bool:
    """Append clinic if not exists. Returns True if appended, False if already present."""
    name = (name or "").strip()
    if not name:
        return False
    clinics = load_clinics()
    if name in clinics:
        return False
    clinics.append(name)
    with open(current_app.config['CLINICS_FILE'], "w", encoding="utf-8") as f:
        json.dump(clinics, f, ensure_ascii=False, indent=2)
    # refresh in-memory copy used by Jinja
    current_app.config['CLINICS_LIST'] = clinics
    return True

# ---- Koopa (HMO) helpers ----
def _ensure_koopa_file_path():
    """Ensure KOOPA_FILE path exists in config; default next to CLINICS_FILE or /data/koopa.json."""
    path = current_app.config.get('KOOPA_FILE')
    if not path:
        clinics_path = current_app.config.get('CLINICS_FILE')
        if clinics_path:
            base_dir = os.path.dirname(clinics_path)
        else:
            base_dir = os.path.join(current_app.root_path, 'data')
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, 'koopa.json')
        current_app.config['KOOPA_FILE'] = path
    return path

def load_koopa():
    """Read koopa list from koopa.json; return [] if missing/empty."""
    path = _ensure_koopa_file_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        current_app.config['KOOPA_LIST'] = []
        return []

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            data = data if isinstance(data, list) else []
        except json.JSONDecodeError:
            data = []
    current_app.config['KOOPA_LIST'] = data
    return data

def append_koopa(name: str) -> bool:
    """Append a koopa if not present. Returns True if appended (file updated), False if already existed/invalid."""
    name = (name or '').strip()
    if not name:
        return False
    koopa_list = load_koopa()
    if name in koopa_list:
        return False
    koopa_list.append(name)
    with open(_ensure_koopa_file_path(), "w", encoding="utf-8") as f:
        json.dump(koopa_list, f, ensure_ascii=False, indent=2)
    current_app.config['KOOPA_LIST'] = koopa_list
    return True

@main.route('/clinics/add', methods=['POST'])
def clinics_add():
    try:
        name = (request.form.get('name') or '').strip()
        if not name:
            return jsonify({'status': 'error', 'message': 'שם מרפאה לא חוקי'}), 400

        # Check if clinic already exists in the DB
        if GilClinics.query.filter_by(clinic_name=name).first():
            return jsonify({'status': 'error', 'message': 'המרפאה כבר קיימת'}), 400

        # Create a new clinic
        new_clinic = GilClinics(clinic_name=name)
        db.session.add(new_clinic)
        db.session.commit()

        return jsonify({'status': 'success', 'name': name})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error adding clinic: {str(e)}'}), 500

@main.route('/koopa/add', methods=['POST'])
def koopa_add():
    try:
        name = (request.form.get('name') or '').strip()
        if not name:
            return jsonify({'status': 'error', 'message': 'שם קופה לא חוקי'}), 400

        # Check if koopa already exists in the DB
        if GilKoopa.query.filter_by(koopa_name=name).first():
            return jsonify({'status': 'error', 'message': 'הקופה כבר קיימת'}), 400

        # Create a new koopa
        new_koopa = GilKoopa(koopa_name=name)
        db.session.add(new_koopa)
        db.session.commit()

        return jsonify({'status': 'success', 'name': name})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error adding koopa: {str(e)}'}), 500

@main.route('/contacts/add', methods=['POST'])
def add_contact():
    try:
        insured_id = request.form.get('insured_id', type=int)
        if not insured_id:
            return jsonify({'status': 'error', 'message': 'insured_id נדרש'}), 400

        contact = GilContact(
            insured_id=insured_id,
            full_name=request.form.get('full_name', ''),
            relation=request.form.get('relation'),
            address=request.form.get('address'),
            phone_1=request.form.get('phone_1'),
            phone_2=request.form.get('phone_2'),
            social_media_1=request.form.get('social_media_1'),
            social_media_2=request.form.get('social_media_2'),
            notes=request.form.get('notes')
        )
        db.session.add(contact)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'contact': {
                'id': contact.id,
                'full_name': contact.full_name,
                'relation': contact.relation,
                'phone_1': contact.phone_1,
                'phone_2': contact.phone_2,
                'social_media_1': contact.social_media_1,
                'social_media_2': contact.social_media_2,
                'notes': contact.notes
            }
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"add_contact error: {e}")
        return jsonify({'status': 'error', 'message': 'שגיאה בהוספת מקושר'}), 500

@main.route('/contacts/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    contact = GilContact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'status': 'success'})

@main.route('/insured/<int:insured_id>/status', methods=['POST'])
def update_insured_status(insured_id):
    try:
        new_status = (request.form.get('status') or '').strip()
        allowed = {'פתוחה', 'בעבודה', 'הושלמה'}
        if new_status not in allowed:
            return jsonify({'status': 'error', 'message': 'סטטוס לא חוקי'}), 400

        insured = GilInsured.query.get_or_404(insured_id)
        insured.status = new_status
        db.session.commit()

        return jsonify({'status': 'success', 'new_status': new_status})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating status for insured {insured_id}: {e}')
        return jsonify({'status': 'error', 'message': 'שגיאה בעדכון סטטוס'}), 500

# === AJAX endpoint to toggle only parkinson_ind ===
@main.route('/insured/<int:insured_id>/parkinson', methods=['POST'])
def update_parkinson(insured_id):
    try:
        insured = GilInsured.query.get_or_404(insured_id)
        value = request.form.get('value', '0')
        insured.parkinson_ind = 1 if value in ('1', 'true', 'on') else 0
        db.session.commit()
        return jsonify({"status": "success", "parkinson_ind": insured.parkinson_ind})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating parkinson_ind for insured {insured_id}: {e}")
        return jsonify({"status": "error", "message": "שגיאה בעדכון נוהל פרקינסון"}), 500

@main.route('/insured/export_rows', methods=['POST'])
def insured_export_rows():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    columns = data.get('columns')  # optional: list of column names; if None, use a default set

    if not ids:
        return jsonify({'status': 'error', 'message': 'לא נבחרו רשומות'}), 400

    # Choose columns (you can change this list later or accept it from the client)
    default_cols = [
        'id', 'received_date', 'ref_number', 'investigator', 'first_name', 'last_name',
        'id_number', 'koopa', 'insurance', 'claim_type', 'claim_number', 'gender', 'status'
    ]
    cols = columns or default_cols

    # Hebrew labels (fallback to the key if missing)
    HEB_LABELS = {
        'id': 'מזהה', 'received_date': 'תאריך קבלה', 'ref_number': 'מספר תיק',
        'investigator': 'חוקר/ים', 'first_name': 'שם פרטי', 'last_name': 'שם משפחה',
        'id_number': 'ת.ז', 'koopa': 'קופה', 'insurance': 'ביטוח', 'claim_type': 'סוג חקירה',
        'claim_number': 'מספר תביעה', 'gender': 'מגדר', 'status': 'סטטוס',
    }

    q = GilInsured.query.filter(GilInsured.id.in_(ids))
    rows = []
    for ins in q:
        rec = {}
        for c in cols:
            rec[c] = getattr(ins, c, '')
        rows.append(rec)

    headers = [{'key': c, 'label': HEB_LABELS.get(c, c)} for c in cols]
    return jsonify({'status': 'success', 'headers': headers, 'rows': rows})

@main.route('/appointments/<int:case_id>', methods=['GET'])
def get_case_appointments(case_id):
    sql = text("""
        SELECT
            a.id,
            a.case_id,
            a.appointment_date,
            a.time_from,
            a.time_to,
            a.status,
            a.address,
            a.notes,
            a.place,
            a.doctor,
            a.koopa,
            GROUP_CONCAT(ia.investigator_id ORDER BY ia.investigator_id SEPARATOR ',') AS investigator_ids_csv,
            GROUP_CONCAT(i.full_name ORDER BY ia.investigator_id SEPARATOR ', ')      AS investigator_names
        FROM gil_appointments a
        LEFT JOIN gil_investigator_appointments ia
               ON ia.appointment_id = a.id
        LEFT JOIN gil_investigator i
               ON i.id = ia.investigator_id
        WHERE a.case_id = :case_id
        GROUP BY a.id
        ORDER BY a.appointment_date, a.time_from
    """)
    rows = db.session.execute(sql, {"case_id": case_id}).mappings().all()

    results = []
    for row in rows:
        ids_csv = row["investigator_ids_csv"]
        investigator_ids = [int(x) for x in ids_csv.split(',')] if ids_csv else []
        results.append({
            "id": row["id"],
            "case_id": row["case_id"],
            "appointment_date": row["appointment_date"].isoformat() if row["appointment_date"] else "",
            "time_from": normalize_time(row["time_from"]),
            "time_to": normalize_time(row["time_to"]),
            "status": row["status"] or "",
            "address": row["address"] or "",
            "place": row["place"] or "",
            "doctor": row["doctor"] or "",
            "koopa": row["koopa"] or "",
            "notes": row["notes"] or "",
            "investigator_ids": investigator_ids,
            "investigators": row["investigator_names"] or ""
        })

    return jsonify(results)

@main.route('/appointments/create', methods=['POST'])
def create_appointment():
    data = request.get_json(force=True, silent=True)
    current_app.logger.info(f"Incoming /appointments/create payload: {data}")

    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    try:
        user_data = json.loads(session.get('user')) if session.get('user') else {}
        user_id = user_data.get('id')

        # --- Parse appointment_date ---
        appt_date = datetime.strptime(data['appointment_date'], "%Y-%m-%d").date()

        # --- Parse times safely (returns datetime.time) ---
        def parse_time(val: str):
            if not val:
                return None
            try:
                return datetime.strptime(val, "%H:%M").time()
            except ValueError:
                try:
                    return datetime.strptime(val, "%H:%M:%S").time()
                except ValueError:
                    return None

        time_from = parse_time(data.get('time_from'))
        time_to = parse_time(data.get('time_to'))

        appt = GilAppointment(
            case_id=int(data['case_id']),
            appointment_date=appt_date,
            time_from=time_from,     # ✅ store as time
            time_to=time_to,         # ✅ store as time
            address=data.get('address'),
            place=data.get('place'),
            doctor=data.get('doctor'),
            koopa=data.get('koopa'),
            status=data.get('status', 'נוצר'),
            notes=data.get('notes')
        )
        db.session.add(appt)
        db.session.flush()

        inv_ids = data.get('investigators', []) or []
        for inv_id in inv_ids:
            db.session.add(GilInvestigatorAppointment(
                appointment_id=appt.id,
                investigator_id=int(inv_id),
                assigned_by=user_id
            ))

        db.session.commit()

        return jsonify({"status": "success", "appointment_id": appt.id})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"create_appointment error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


@main.route('/appointments/<int:id>/delete', methods=['POST'])
def delete_appointment(id):
    try:
        appt = GilAppointment.query.get_or_404(id)

        # delete investigator links first
        GilInvestigatorAppointment.query.filter_by(appointment_id=id).delete()

        db.session.delete(appt)
        db.session.commit()

        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"delete_appointment error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Single appointment as JSON ---
@main.route('/appointments/<int:id>/get', methods=['GET'])
@main.route('/appointments/<int:id>/json', methods=['GET'])
def get_appointment_json(id):
    appt = GilAppointment.query.get_or_404(id)

    # fetch linked investigators
    inv_links = GilInvestigatorAppointment.query.filter_by(appointment_id=appt.id).all()
    investigator_ids = [link.investigator_id for link in inv_links]
    investigator_names = [link.investigator.full_name for link in inv_links if link.investigator]

    data = {
        "id": appt.id,
        "case_id": appt.case_id,
        "appointment_date": appt.appointment_date.isoformat() if appt.appointment_date else "",
        "time_from": normalize_time(appt.time_from),
        "time_to": normalize_time(appt.time_to),
        "status": appt.status or "",
        "place": appt.place or "",
        "doctor": appt.doctor or "",
        "koopa": appt.koopa or "",
        "address": appt.address or "",
        "notes": appt.notes,
        "investigator_ids": investigator_ids,
        "investigators": ", ".join(investigator_names)
    }
    return jsonify(data)



@main.route('/appointments/<int:id>/update', methods=['POST'])
def update_appointment(id):
    data = request.get_json()
    appt = GilAppointment.query.get_or_404(id)

    try:
        # --- Parse appointment_date (date only) ---
        if data.get('appointment_date'):
            appt.appointment_date = datetime.strptime(data['appointment_date'], "%Y-%m-%d").date()

        # --- Safe parse for TIME columns ---
        def parse_time(val: str):
            if not val:
                return None
            try:
                return datetime.strptime(val, "%H:%M").time()
            except ValueError:
                try:
                    return datetime.strptime(val, "%H:%M:%S").time()
                except ValueError:
                    return None

        appt.time_from = parse_time(data.get('time_from'))
        appt.time_to = parse_time(data.get('time_to'))

        # --- Update other fields ---
        appt.address = data.get('address')
        appt.place = data.get('place')
        appt.doctor = data.get('doctor')
        appt.koopa = data.get('koopa')
        appt.status = data.get('status', appt.status)
        appt.notes = data.get('notes')

        # --- Reset investigators ---
        GilInvestigatorAppointment.query.filter_by(appointment_id=id).delete()
        inv_ids = data.get('investigators', [])
        user_data = json.loads(session.get('user')) if session.get('user') else {}
        user_id = user_data.get('id')
        for inv_id in inv_ids:
            db.session.add(GilInvestigatorAppointment(
                appointment_id=id,
                investigator_id=int(inv_id),
                assigned_by=user_id
            ))

        db.session.commit()
        return jsonify({"status": "success"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"update_appointment error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400



@main.route('/appointments/<int:case_id>/has_future', methods=['GET'])
def has_future_appointment(case_id):
    today = datetime.utcnow().date()
    exists = db.session.query(
        GilAppointment.query.filter(
            GilAppointment.case_id == case_id,
            GilAppointment.appointment_date >= today
        ).exists()
    ).scalar()
    return jsonify({"has_future": bool(exists)})

@main.route('/appointments/all', methods=['GET'])
def get_all_appointments():
    """
    Fetch ALL appointments (with insured, insurance, type, and investigators).
    """
    sql = text("""
        SELECT
            a.id,
            a.case_id,
            ins.ref_number,
            a.appointment_date,
            a.time_from,
            a.time_to,
            a.status,
            a.address,
            a.notes,
            ins.first_name,
            ins.last_name,
            ins.insurance AS insurance,
            ins.claim_type AS insurance_type,
            COALESCE(GROUP_CONCAT(i.full_name ORDER BY ia.investigator_id SEPARATOR ', '), '') AS investigator_names
        FROM gil_appointments a
        LEFT JOIN gil_insured ins
               ON ins.id = a.case_id
        LEFT JOIN gil_investigator_appointments ia
               ON ia.appointment_id = a.id
        LEFT JOIN gil_investigator i
               ON i.id = ia.investigator_id
        GROUP BY a.id
        ORDER BY a.appointment_date, a.time_from
    """)

    rows = db.session.execute(sql).mappings().all()

    results = []
    for row in rows:
        investigator_names = row["investigator_names"] or ""

        # Build full event title
        title_parts = [
            f"{normalize_time(row['time_from'])}-{normalize_time(row['time_to'])}",
            f"תיק {row['ref_number']}",
            f"{row['first_name']} {row['last_name']}",
            row["insurance"] or "",
            row["insurance_type"] or "",
            investigator_names
        ]
        title = " ".join([part for part in title_parts if part.strip()])

        results.append({
            "id": row["id"],
            "case_id": row["case_id"],
            "appointment_date": row["appointment_date"].isoformat() if row["appointment_date"] else "",
            "time_from": normalize_time(row["time_from"]),
            "time_to": normalize_time(row["time_to"]),
            "status": row["status"] or "",
            "address": row["address"] or "",
            "notes": row["notes"] or "",
            "investigators": investigator_names,
            "title": title   # ✅ send prebuilt title for calendar
        })

    return jsonify(results)




@main.route('/appointments/calendar')
def appointments_calendar():
    # load user
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    # load roles
    roles = db.session.query(TocRole).all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    return render_template("calendar.html", user=user, roles=roles_list)





#########################
# GET ALL INVESTIGATORS #
#########################
@main.route('/api/get_investigators', methods=['GET'])
def get_investigators():
    investigators = GilInvestigator.query.all()
    results = []
    for inv in investigators:
        # find linked user by email/username
        user = User.query.filter_by(email=inv.email, role="Investigator").first()
        results.append({
            "id": inv.id,
            "first_name": inv.full_name.split(" ")[0] if inv.full_name else "",
            "last_name": " ".join(inv.full_name.split(" ")[1:]) if inv.full_name else "",
            "address": inv.address,
            "phone": inv.phone,
            "email": inv.email,
            "start_work": inv.start_work.strftime("%Y-%m-%d") if inv.start_work else "",
            "username": user.username if user else "",
            "role": user.role if user else "Investigator",
            "shop": user.shop if user else "Head Office"
        })
    return jsonify(results)

#########################
# GET SINGLE INVESTIGATOR #
#########################
from datetime import datetime

@main.route('/investigators')
def investigators():
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    if not user or user.get("role") != "Investigator":
        return redirect(url_for('main.login'))

    # Find investigator record
    inv_row = GilInvestigator.query.filter_by(user_id=user["id"]).first()
    if not inv_row:
        full_name = f"{user.get('first_name','').strip()} {user.get('last_name','').strip()}".strip()
        inv_row = GilInvestigator.query.filter_by(full_name=full_name).first()

    cases = []
    if inv_row:
        query = (
            db.session.query(GilInsured)
            .join(GilInvestigatorCase, GilInsured.id == GilInvestigatorCase.insured_id)
            .filter(
                GilInvestigatorCase.investigator_id == inv_row.id,
                GilInvestigatorCase.active.is_(True),
                GilInsured.status != "הושלמה"
            )
        )
        cases = query.order_by(GilInsured.received_date.desc()).all()

        # --- Add future appointments flag for each case ---
        today = datetime.utcnow().date()
        for c in cases:
            c.has_future_appointments = (
                    db.session.query(GilAppointment.id)
                    .filter(
                        GilAppointment.case_id == c.id,
                        GilAppointment.appointment_date != None,
                        GilAppointment.appointment_date > today
                    )
                    .first()
                    is not None
            )

    # Context for template
    investigators = GilInvestigator.query.order_by(GilInvestigator.full_name.asc()).all()
    koopa_list = GilKoopa.query.order_by(GilKoopa.koopa_name.asc()).all()
    roles = db.session.query(TocRole).all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    return render_template(
        'investigators.html',
        user=user,
        shop=shop,
        roles=roles_list,
        cases=cases,
        investigators=investigators,
        koopa_list=koopa_list
    )


#########################
# CREATE INVESTIGATOR   #
#########################
@main.route('/api/create_investigator', methods=['POST'])
def create_investigator():
    data = request.form
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    full_name = f"{first_name} {last_name}".strip()

    # check if user already exists
    existing_user = User.query.filter_by(email=data.get("email")).first()
    if existing_user:
        return jsonify({
            "status": "error",
            "message": f"User with email {data.get('email')} already exists"
        }), 400

    # create linked user first
    user = User(
        username=data.get("username"),
        password=data.get("password"),
        first_name=first_name,
        last_name=last_name,
        email=data.get("email"),
        phone=data.get("phone"),
        role="Investigator",
        shop="Head Office"
    )
    db.session.add(user)
    db.session.flush()  # get user.id

    # create investigator linked to user
    inv = GilInvestigator(
        full_name=full_name,
        address=data.get("address"),
        phone=data.get("phone"),
        email=data.get("email"),
        start_work=datetime.strptime(data.get("start_work"), "%Y-%m-%d") if data.get("start_work") else None,
        active_status="Active",
        user_id=user.id  # 🔗 reference
    )
    db.session.add(inv)

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Investigator and user created",
        "id": inv.id,
        "user_id": user.id
    })

#########################
# UPDATE INVESTIGATOR   #
#########################
@main.route('/api/update_investigator/<int:id>', methods=['PUT'])
def update_investigator(id):
    data = request.form
    inv = GilInvestigator.query.get_or_404(id)

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    inv.full_name = f"{first_name} {last_name}".strip()
    inv.address = data.get("address")
    inv.phone = data.get("phone")
    inv.email = data.get("email")
    inv.start_work = datetime.strptime(data.get("start_work"), "%Y-%m-%d") if data.get("start_work") else None

    # update linked user
    user = User.query.filter_by(email=inv.email, role="Investigator").first()
    if not user:
        # if not found, create new
        user = User(role="Investigator", shop="Head Office")
        db.session.add(user)

    user.username = data.get("username")
    user.password = data.get("password")
    user.first_name = first_name
    user.last_name = last_name
    user.email = data.get("email")
    user.phone = data.get("phone")

    db.session.commit()
    return jsonify({"status": "success", "message": "Investigator updated"})

#########################
# DELETE INVESTIGATOR   #
#########################
@main.route('/api/delete_investigator/<int:id>', methods=['DELETE'])
def delete_investigator(id):
    inv = GilInvestigator.query.get_or_404(id)

    # delete linked user
    if inv.email:
        user = User.query.filter_by(email=inv.email, role="Investigator").first()
        if user:
            db.session.delete(user)

    db.session.delete(inv)
    db.session.commit()
    return jsonify({"status": "success", "message": "Investigator deleted"})

@main.route('/case/<int:case_id>/accept', methods=['POST'])
def accept_case(case_id):
    case = GilInsured.query.get_or_404(case_id)
    case.status = "בעבודה"
    db.session.commit()
    return jsonify({"status": "success", "message": "התיק התקבל בהצלחה"})

@main.route('/case/<int:case_id>/complete', methods=['POST'])
def complete_case(case_id):
    case = GilInsured.query.get_or_404(case_id)
    case.status = "הושלמה"
    db.session.commit()
    return jsonify({"status": "success", "message": "התיק הושלם בהצלחה"})


@main.route('/appointments/<int:id>/assign_investigators', methods=['POST'])
def assign_investigators(id):
    data = request.json
    GilInvestigatorAppointment.query.filter_by(appointment_id=id).delete()
    for inv_id in data.get('investigators', []):
        link = GilInvestigatorAppointment(
            appointment_id=id,
            investigator_id=inv_id,
            assigned_by=session.get('user_id')
        )
        db.session.add(link)
    db.session.commit()
    return jsonify({"status": "success"})

### Tasks management

@main.route('/tasks/<int:case_id>', methods=['GET'])
def get_case_tasks(case_id):
    """
    Fetch all tasks for a given case_id, including investigator + creator names.
    """
    sql = text("""
        SELECT
            t.id,
            t.case_id,
            t.title,
            t.description,
            t.due_date,
            t.status,
            t.investigator_id,
            i.full_name AS investigator_name,
            t.creator_id,
            u.username AS creator_name,
            t.date_created,
            t.date_modified
        FROM gil_tasks t
        LEFT JOIN gil_investigator i ON i.id = t.investigator_id
        LEFT JOIN toc_users u ON u.id = t.creator_id
        WHERE t.case_id = :case_id
        ORDER BY t.due_date, t.id
    """)

    rows = db.session.execute(sql, {"case_id": case_id}).mappings().all()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "case_id": row["case_id"],
            "title": row["title"] or "",
            "description": row["description"] or "",
            "due_date": str(row["due_date"]) if row["due_date"] else "",
            "status": row["status"] or "",
            "investigator_id": row["investigator_id"],
            "investigator_name": row["investigator_name"] or "",
            "creator_id": row["creator_id"],
            "creator_name": row["creator_name"] or "",
            "date_created": row["date_created"].isoformat() if row["date_created"] else "",
            "date_modified": row["date_modified"].isoformat() if row["date_modified"] else ""
        })

    return jsonify(results)


@main.route('/tasks/<int:task_id>/json', methods=['GET'])
def get_task_json(task_id):
    task = GilTask.query.get_or_404(task_id)

    insured = GilInsured.query.get(task.case_id)  # task.case_id -> gil_insured.id

    insured_name = "—"
    case_ref = None

    if insured:
        insured_name = f"{(insured.first_name or '').strip()} {(insured.last_name or '').strip()}".strip() or "—"
        case_ref = (insured.ref_number or "").strip() or None

    return jsonify({
        "id": task.id,
        "case_id": task.case_id,
        "title": task.title,
        "description": task.description or "",
        "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
        "status": task.status or "",
        "investigator_id": task.investigator_id,

        # ✅ for UI
        "insured_name": insured_name,
        "case_ref": case_ref,   # e.g. 67799
    })

@main.route('/tasks/create', methods=['POST'])
def create_task():
    try:
        user_data = json.loads(session.get('user')) if session.get('user') else {}
        creator_id = user_data.get('id') if user_data else None

        task = GilTask(
            case_id=request.form.get('case_id'),
            investigator_id=request.form.get('investigator_id'),
            title=request.form.get('title'),
            description=request.form.get('description'),
            due_date=request.form.get('due_date'),
            status=request.form.get('status'),
            creator_id=creator_id
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({"status": "success", "message": "Task created"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"create_task error: {e}")
        return jsonify({"status": "error", "message": str(e)})


@main.route('/tasks/bulk_create', methods=['POST'])
def bulk_create_tasks():
    """Create the same task for multiple insured cases (admin bulk action)."""
    try:
        user_data = json.loads(session.get('user')) if session.get('user') else {}
        creator_id = user_data.get('id') if user_data else None
        if not creator_id:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        payload = request.get_json(silent=True) or {}
        case_ids = payload.get("case_ids") or []

        # basic validation
        if not isinstance(case_ids, list) or not case_ids:
            return jsonify({"status": "error", "message": "case_ids is required"}), 400

        title = (payload.get("title") or "").strip()
        if not title:
            return jsonify({"status": "error", "message": "title is required"}), 400

        investigator_id = payload.get("investigator_id") or None
        description = (payload.get("description") or "").strip()
        status = (payload.get("status") or "פתוחה").strip() or "פתוחה"

        due_date = None
        due_date_str = (payload.get("due_date") or "").strip()
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid due_date format (expected YYYY-MM-DD)"}), 400

        created = 0
        # create tasks
        for cid in case_ids:
            try:
                cid_int = int(cid)
            except Exception:
                continue

            task = GilTask(
                case_id=cid_int,
                investigator_id=int(investigator_id) if investigator_id else None,
                title=title,
                description=description,
                due_date=due_date,
                status=status,
                creator_id=creator_id
            )
            db.session.add(task)
            created += 1

        db.session.commit()
        return jsonify({"status": "success", "created": created})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"bulk_create_tasks error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@main.route('/tasks/<int:id>/update', methods=['POST'])
def update_task(id):
    try:
        task = GilTask.query.get(id)
        if not task:
            return jsonify({"status": "error", "message": "Task not found"})

        task.title = request.form.get('title')
        task.description = request.form.get('description')
        task.investigator_id = request.form.get('investigator_id')

        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid date format"}), 400

        task.status = request.form.get('status')
        db.session.commit()

        return jsonify({"status": "success", "message": "Task updated"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"update_task error: {e}")
        return jsonify({"status": "error", "message": str(e)})



@main.route('/tasks/<int:id>/delete', methods=['POST'])
def delete_task(id):
    try:
        task = GilTask.query.get(id)
        if not task:
            return jsonify({"status": "error", "message": "Task not found"})

        db.session.delete(task)
        db.session.commit()
        return jsonify({"status": "success", "message": "Task deleted"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)})


# Admin appointments
@main.route('/admin_appointments')
def admin_appointments():
    # session context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    # roles
    roles = db.session.query(TocRole).all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    # appointments
    sql = text("""
        SELECT 
            a.id,
            a.case_id,
            a.appointment_date,
            a.time_from,
            a.time_to,
            a.status,
            a.address,
            a.notes,
            ins.first_name,
            ins.last_name,
            ins.insurance,
            ins.claim_type,
            COALESCE(GROUP_CONCAT(i.full_name SEPARATOR ', '), '') AS investigators
        FROM gil_appointments a
        LEFT JOIN gil_insured ins ON ins.id = a.case_id
        LEFT JOIN gil_investigator_appointments ia ON ia.appointment_id = a.id
        LEFT JOIN gil_investigator i ON i.id = ia.investigator_id
        GROUP BY a.id
        ORDER BY a.appointment_date DESC, a.time_from
    """)
    rows = db.session.execute(sql).mappings().all()

    # investigators for dropdown
    investigators = GilInvestigator.query.order_by(GilInvestigator.full_name.asc()).all()
    investigators_list = [{"id": i.id, "full_name": i.full_name} for i in investigators]

    return render_template(
        'appointments_admin.html',
        appointments=rows,
        user=user,
        shop=shop,
        roles=roles_list,
        investigators=investigators_list   # ✅ inject into template
    )


@main.route('/appointments/<int:appointment_id>/details_json')
def get_appointment_details_json(appointment_id):
    sql = text("""
        SELECT 
            a.id,
            a.case_id,
            a.appointment_date,
            a.time_from,
            a.time_to,
            a.status,
            a.address,
            a.place,
            a.doctor,
            a.koopa,
            a.notes,
            ins.first_name,
            ins.last_name,
            ins.insurance,
            ins.claim_type,
            COALESCE(GROUP_CONCAT(ia.investigator_id), '') AS investigator_ids
        FROM gil_appointments a
        LEFT JOIN gil_insured ins ON ins.id = a.case_id
        LEFT JOIN gil_investigator_appointments ia ON ia.appointment_id = a.id
        WHERE a.id = :appointment_id
        GROUP BY a.id
    """)

    row = db.session.execute(sql, {"appointment_id": appointment_id}).mappings().first()

    if not row:
        return jsonify({"status": "error", "message": "Appointment not found"}), 404

    investigator_ids = [int(x) for x in row["investigator_ids"].split(',') if x]

    return jsonify({
        "id": row["id"],
        "case_id": row["case_id"],
        "appointment_date": row["appointment_date"].isoformat() if row["appointment_date"] else "",
        "time_from": str(row["time_from"]),
        "time_to": str(row["time_to"]),
        "status": row["status"],
        "address": row["address"],
        "place": row["place"],
        "doctor": row["doctor"],
        "koopa": row["koopa"],
        "notes": row["notes"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "insurance": row["insurance"],
        "claim_type": row["claim_type"],
        "investigator_ids": investigator_ids
    })

#### Task amdin

# Admin tasks
@main.route('/admin_tasks')
def admin_tasks():
    # session context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    # roles
    roles = db.session.query(TocRole).all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    sql = text("""
        SELECT 
            t.id,
            t.case_id,
            t.title,
            t.description,
            t.due_date,
            t.status,
            t.date_created,
            t.creator_id,
            i.full_name AS investigator_name
        FROM gil_tasks t
        LEFT JOIN gil_investigator i ON i.id = t.investigator_id
        ORDER BY t.date_created DESC
    """)
    rows = db.session.execute(sql).mappings().all()

    # Also fetch all investigators for dropdown
    investigators = db.session.execute(text("""
        SELECT id, full_name FROM gil_investigator ORDER BY full_name ASC
    """)).mappings().all()

    return render_template(
        'tasks_admin.html',
        tasks=rows,
        investigators=investigators,
        user=user,
        shop=shop,
        roles=roles_list
    )


# Admin task JSON
@main.route('/admin_tasks/<int:task_id>/json')
def get_admin_task_json(task_id):
    sql = text("""
        SELECT 
            t.id,
            t.case_id,
            t.title,
            t.description,
            t.due_date,
            t.status,
            t.investigator_id
        FROM gil_tasks t
        WHERE t.id = :task_id
    """)
    row = db.session.execute(sql, {"task_id": task_id}).mappings().first()

    if not row:
        return jsonify({"status": "error", "message": "Task not found"}), 404

    return jsonify({
        "id": row["id"],
        "case_id": row["case_id"],
        "title": row["title"],
        "description": row["description"],
        "due_date": row["due_date"].isoformat() if row["due_date"] else "",
        "status": row["status"],
        "investigator_id": row["investigator_id"]
    })

# Admin task update
@main.route('/admin_tasks/<int:task_id>/update', methods=['POST'])
def update_admin_task(task_id):
    data = request.get_json()

    sql = text("""
        UPDATE gil_tasks
        SET 
            title = :title,
            description = :description,
            due_date = :due_date,
            status = :status,
            investigator_id = :investigator_id,
            date_modified = NOW()
        WHERE id = :task_id
    """)

    db.session.execute(sql, {
        "title": data.get("title"),
        "description": data.get("description"),
        "due_date": data.get("due_date"),
        "status": data.get("status"),
        "investigator_id": data.get("investigator_id"),
        "task_id": task_id
    })
    db.session.commit()

    return jsonify({"status": "success", "message": "Task updated successfully"})


####################  TRACKING REPORTS  #####################


@main.route("/api/tracking_reports", methods=["GET"])
def api_tracking_reports_list():
    try:
        insured_id = request.args.get("insured_id", type=int)
        ref_number = (request.args.get("ref_number") or "").strip()
        report_date = (request.args.get("report_date") or "").strip()  # optional

        if not insured_id or not ref_number:
            return jsonify({"status": "error", "message": "insured_id/ref_number missing"}), 400

        allowed, inv_row, user = require_case_access_or_403(insured_id, ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        q = GilTrackingReport.query.filter_by(insured_id=insured_id, ref_number=ref_number)

        d = parse_date_flexible(report_date)
        if d:
            q = q.filter(GilTrackingReport.report_date == d)

        rows = q.order_by(GilTrackingReport.report_date.desc(), GilTrackingReport.report_id.desc()).all()

        return jsonify({
            "status": "success",
            "reports": [{
                "report_id": r.report_id,
                "insured_id": r.insured_id,
                "ref_number": r.ref_number,
                "investigator_id": r.investigator_id,
                "report_date": normalize_date(r.report_date),
                "status": r.status or "Draft",
                "note": r.note or "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            } for r in rows]
        })

    except Exception as e:
        current_app.logger.error(f"api_tracking_reports_list error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


from sqlalchemy import func

@main.route("/api/tracking_reports/<int:report_id>", methods=["GET"])
def api_tracking_report_get(report_id):
    try:
        r = GilTrackingReport.query.get_or_404(report_id)

        allowed, inv_row, user = require_case_access_or_403(r.insured_id, r.ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        req_source = (request.args.get("source") or "").strip().lower()
        if req_source not in ("admin", "investigator", ""):
            return jsonify({"status": "error", "message": "Invalid source"}), 400

        items_q = GilTrackingReportActivity.query.filter_by(report_id=r.report_id)

        # ✅ Filter by source (insured page = investigator, editor = admin)
        if req_source:
            items_q = items_q.filter(GilTrackingReportActivity.source == req_source)

            # ✅ Show latest set for that source
            max_set = db.session.query(func.max(GilTrackingReportActivity.set_no)) \
                .filter(GilTrackingReportActivity.report_id == r.report_id,
                        GilTrackingReportActivity.source == req_source) \
                .scalar()

            if max_set is not None:
                items_q = items_q.filter(GilTrackingReportActivity.set_no == max_set)

        items = items_q.order_by(
            GilTrackingReportActivity.sort_order.asc(),
            GilTrackingReportActivity.activity_id.asc()
        ).all()

        expenses = GilTrackingExpense.query.filter_by(report_id=r.report_id, deleted_ind=False) \
            .order_by(GilTrackingExpense.expense_date.asc(), GilTrackingExpense.expense_id.asc()) \
            .all()

        exp_out = []
        total = 0
        for e in expenses:
            media = GilTrackingExpenseMedia.query.filter_by(expense_id=e.expense_id) \
                .order_by(GilTrackingExpenseMedia.media_id.asc()) \
                .all()

            amt = float(e.amount or 0)
            total += amt

            exp_out.append({
                "expense_id": e.expense_id,
                "expense_date": normalize_date(e.expense_date),
                "description": e.description or "",
                "amount": f"{amt:.2f}",
                "currency": e.currency or "ILS",
                "category": e.category or "",
                "media": [{
                    "media_id": m.media_id,
                    "file_name": m.file_name or "",
                    "dropbox_path": m.dropbox_path or "",
                    "shared_url": m.shared_url or "",
                    "thumb_url": m.thumb_url or ""
                } for m in media]
            })

        return jsonify({
            "status": "success",
            "report": {
                "report_id": r.report_id,
                "insured_id": r.insured_id,
                "ref_number": r.ref_number,
                "investigator_id": r.investigator_id,
                "report_date": normalize_date(r.report_date),
                "status": r.status or "Draft",
                "note": r.note or "",
                "mileage_km": r.mileage_km,
                "items": [{
                    "activity_id": it.activity_id,
                    "activity_time": normalize_time(it.activity_time),
                    "description": it.description or "",
                    "sort_order": int(it.sort_order or 0),
                    "source": it.source  # optional, but useful for debugging
                } for it in items],
                "expenses": exp_out,
                "expenses_total": f"{total:.2f}"
            }
        })

    except Exception as e:
        current_app.logger.error(f"api_tracking_report_get error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500



@main.route("/api/tracking_reports/save", methods=["POST"])
def api_tracking_report_save():
    """
    Saves a tracking report + activities + expenses.

    IMPORTANT BEHAVIOR (per your new rule):
    - We KEEP Start/End in DB.
    - We DO NOT delete all activities for the report.
    - We version activities PER SOURCE using (source, set_no, is_current).
      * Investigator save -> source='investigator'
      * Admin/Manager save -> source='admin'
    - On save: previous sets for that source are marked is_current=0, new set inserted as is_current=1.
    """
    try:
        from datetime import datetime
        from decimal import Decimal, InvalidOperation
        from sqlalchemy import func

        payload = request.get_json(silent=True) or {}

        insured_id = payload.get("insured_id")
        ref_number = (payload.get("ref_number") or "").strip()
        report_date_in = (payload.get("report_date") or "").strip()
        note = (payload.get("note") or "").strip()
        items = payload.get("items") or []
        report_id = payload.get("report_id")  # optional

        expenses_in = payload.get("expenses") or []
        deleted_expense_ids = payload.get("deleted_expense_ids") or []

        # -----------------------------
        # mileage validation
        # -----------------------------
        mileage_in = payload.get("mileage_km", None)
        mileage_km = None
        try:
            if mileage_in not in (None, "", "null"):
                mileage_km = int(mileage_in)
                if mileage_km < 0:
                    return jsonify({"status": "error", "message": "Invalid mileage_km"}), 400
        except Exception:
            return jsonify({"status": "error", "message": "Invalid mileage_km"}), 400

        if not insured_id or not ref_number or not report_date_in:
            return jsonify({"status": "error", "message": "insured_id/ref_number/report_date missing"}), 400

        d = parse_date_flexible(report_date_in)
        if not d:
            return jsonify({"status": "error", "message": "Invalid report_date"}), 400

        allowed, inv_row, user = require_case_access_or_403(int(insured_id), ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        # -----------------------------
        # Load existing report (by report_id OR by (insured_id, ref_number, report_date))
        # -----------------------------
        r = None
        if report_id:
            r = GilTrackingReport.query.get(report_id)

        if not r:
            r = GilTrackingReport.query.filter_by(
                insured_id=int(insured_id),
                ref_number=ref_number,
                report_date=d
            ).first()

        # Final => cannot edit for non-admin/manager
        if r and (r.status == "Final") and (not user_is_admin_or_manager(user)):
            return jsonify({"status": "error", "message": "Report is Final and cannot be edited"}), 403

        # -----------------------------
        # Determine investigator_id
        # -----------------------------
        investigator_id = None

        if user_is_admin_or_manager(user):
            investigator_id = payload.get("investigator_id")

            if not investigator_id and r:
                investigator_id = r.investigator_id

            if not investigator_id:
                inv2 = get_current_investigator_row()
                if inv2:
                    investigator_id = inv2.id

            if not investigator_id:
                return jsonify({
                    "status": "error",
                    "message": "investigator_id missing (admin create). Open as investigator or pass investigator_id."
                }), 400
        else:
            investigator_id = inv_row.id if inv_row else None
            if not investigator_id:
                return jsonify({"status": "error", "message": "investigator_id missing"}), 400

        # -----------------------------
        # Create / update report
        # -----------------------------
        if not r:
            r = GilTrackingReport(
                insured_id=int(insured_id),
                ref_number=ref_number,
                investigator_id=int(investigator_id),
                report_date=d,
                status="Draft",
                note=note,
                mileage_km=mileage_km
            )
            db.session.add(r)
            db.session.flush()  # ensures r.report_id exists
        else:
            # Investigator cannot edit other investigator's report
            if (not user_is_admin_or_manager(user)) and (r.investigator_id != int(investigator_id)):
                return jsonify({"status": "error", "message": "Cannot edit another investigator's report"}), 403

            r.note = note
            r.mileage_km = mileage_km
            r.updated_at = datetime.utcnow()

        # -----------------------------
        # Replace activities (PER SOURCE, versioned)
        # -----------------------------
        user_id = (user or {}).get("id") or None
        source = "admin" if user_is_admin_or_manager(user) else "investigator"

        # next set_no for this report+source
        max_set = db.session.query(func.max(GilTrackingReportActivity.set_no)).filter(
            GilTrackingReportActivity.report_id == r.report_id,
            GilTrackingReportActivity.source == source
        ).scalar()
        next_set_no = int(max_set or 0) + 1

        # mark previous current sets for this source as not current
        GilTrackingReportActivity.query.filter(
            GilTrackingReportActivity.report_id == r.report_id,
            GilTrackingReportActivity.source == source,
            GilTrackingReportActivity.is_current == 1
        ).update(
            {"is_current": 0, "updated_at": datetime.utcnow()},
            synchronize_session=False
        )

        # insert new set
        for idx, it in enumerate(items):
            t = (it.get("activity_time") or "").strip()
            desc = (it.get("description") or "").strip()

            # keep DB clean: ignore empty rows only
            if not t or not desc:
                continue

            t_parsed = parse_time(t)
            if not t_parsed:
                continue

            sort_order = it.get("sort_order")
            if sort_order is None:
                sort_order = idx

            db.session.add(GilTrackingReportActivity(
                report_id=r.report_id,
                set_no=next_set_no,
                is_current=1,
                source=source,
                created_by_user_id=user_id,
                activity_time=t_parsed,
                description=desc,
                sort_order=int(sort_order),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ))

        # -----------------------------
        # Expenses: soft delete + upsert
        # -----------------------------
        if deleted_expense_ids:
            GilTrackingExpense.query.filter(
                GilTrackingExpense.report_id == r.report_id,
                GilTrackingExpense.expense_id.in_(deleted_expense_ids)
            ).update(
                {"deleted_ind": True, "updated_at": datetime.utcnow()},
                synchronize_session=False
            )

        for ex in expenses_in:
            ex_id = ex.get("expense_id")
            ex_desc = (ex.get("description") or "").strip()
            ex_date_in = (ex.get("expense_date") or "").strip()
            ex_category = (ex.get("category") or "").strip() or None
            ex_currency = (ex.get("currency") or "").strip() or "ILS"

            try:
                ex_amount = Decimal(str(ex.get("amount") or "0")).quantize(Decimal("0.01"))
                if ex_amount < 0:
                    return jsonify({"status": "error", "message": "Expense amount cannot be negative"}), 400
            except (InvalidOperation, ValueError):
                return jsonify({"status": "error", "message": "Invalid expense amount"}), 400

            ex_date = parse_date_flexible(ex_date_in) if ex_date_in else None

            # ignore empty expense rows
            if not ex_desc and ex_amount == 0:
                continue

            if ex_id:
                row = GilTrackingExpense.query.filter_by(expense_id=ex_id, report_id=r.report_id).first()
                if not row:
                    continue

                row.description = ex_desc
                row.amount = ex_amount
                row.expense_date = ex_date or row.expense_date
                row.currency = ex_currency
                row.category = ex_category
                row.deleted_ind = False
                row.updated_at = datetime.utcnow()
            else:
                row = GilTrackingExpense(
                    report_id=r.report_id,
                    investigator_id=int(investigator_id),
                    created_by_user_id=user_id,
                    expense_date=ex_date,
                    description=ex_desc,
                    amount=ex_amount,
                    currency=ex_currency,
                    category=ex_category,
                    deleted_ind=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(row)

        db.session.commit()

        # -----------------------------
        # Return expenses WITH DB IDs so UI can upload invoice immediately
        # -----------------------------
        expenses = GilTrackingExpense.query.filter_by(report_id=r.report_id, deleted_ind=False) \
            .order_by(GilTrackingExpense.expense_date.asc(), GilTrackingExpense.expense_id.asc()) \
            .all()

        exp_out = []
        total = 0.0
        for e in expenses:
            amt = float(e.amount or 0)
            total += amt

            media = GilTrackingExpenseMedia.query.filter_by(expense_id=e.expense_id) \
                .order_by(GilTrackingExpenseMedia.media_id.asc()) \
                .all()

            exp_out.append({
                "expense_id": e.expense_id,
                "expense_date": normalize_date(e.expense_date),
                "description": e.description or "",
                "amount": f"{amt:.2f}",
                "currency": e.currency or "ILS",
                "category": e.category or "",
                "media": [{
                    "media_id": m.media_id,
                    "file_name": m.file_name or "",
                    "dropbox_path": m.dropbox_path or "",
                    "shared_url": m.shared_url or "",
                    "thumb_url": m.thumb_url or ""
                } for m in media]
            })

        return jsonify({
            "status": "success",
            "report_id": r.report_id,
            "report_date": normalize_date(r.report_date),
            "status_value": r.status or "Draft",
            "mileage_km": r.mileage_km,
            "saved_source": source,
            "saved_set_no": next_set_no,
            "expenses": exp_out,
            "expenses_total": f"{total:.2f}"
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"api_tracking_report_save error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500




@main.route("/api/tracking_reports/<int:report_id>/status", methods=["POST"])
def api_tracking_report_set_status(report_id):
    try:
        payload = request.get_json(silent=True) or {}
        new_status = (payload.get("status") or "").strip()

        # ✅ add Final
        allowed_status = {"Draft", "Submitted", "Approved", "Rejected", "Final"}
        if new_status not in allowed_status:
            return jsonify({"status": "error", "message": "Invalid status"}), 400

        r = GilTrackingReport.query.get_or_404(report_id)

        allowed, inv_row, user = require_case_access_or_403(r.insured_id, r.ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        # ✅ Only admin/manager can approve/reject
        if new_status in {"Approved", "Rejected"} and (not user_is_admin_or_manager(user)):
            return jsonify({"status": "error", "message": "Only admin can approve/reject"}), 403

        # ✅ Final is allowed for everyone who has access (or if you want: only admin)
        # If you want "Final only admin", uncomment:
        # if new_status == "Final" and (not user_is_admin_or_manager(user)):
        #     return jsonify({"status": "error", "message": "Only admin can set Final"}), 403

        r.status = new_status
        r.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({"status": "success", "report_id": r.report_id, "new_status": r.status})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"api_tracking_report_set_status error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500



@main.route("/api/tracking_reports/<int:report_id>/delete", methods=["POST"])
def api_tracking_report_delete(report_id):
    try:
        r = GilTrackingReport.query.get_or_404(report_id)

        allowed, inv_row, user = require_case_access_or_403(r.insured_id, r.ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        # Optional: prevent deleting approved unless admin
        if r.status == "Approved" and (not user_is_admin_or_manager(user)):
            return jsonify({"status": "error", "message": "Approved report cannot be deleted"}), 400

        if r.status == "Final" and (not user_is_admin_or_manager(user)):
            return jsonify({"status": "error", "message": "Final report cannot be deleted"}), 400


        GilTrackingReportActivity.query.filter_by(report_id=r.report_id).delete()
        db.session.delete(r)
        db.session.commit()

        return jsonify({"status": "success"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"api_tracking_report_delete error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


@main.route('/tracking-report/finalize', methods=['POST'])
def finalize_tracking_report():
    data = request.get_json()
    report_id = data.get('report_id')

    report = GilTrackingReport.query.get_or_404(report_id)
    report.status = 'Final'
    report.last_edited = datetime.utcnow()

    db.session.commit()

    return jsonify({'status': 'ok'})





################  UPLOAD MEDIA BY INVESTIGATORS  #################

# ===============================
# Media upload (Photos / Videos)
# ===============================

MEDIA_SUBFOLDERS = {
    "photos": "תמונות",
    "id_photo": "תמונת זיהוי",
    "social": "מדיה חברתית",
    "video": "וידאו",
    "expenses": "הוצאות",
}

ALLOWED_MEDIA_TYPES = set(MEDIA_SUBFOLDERS.keys())

# Keep it conservative for phase 1
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi"}  # adjust as needed

MAX_FILES_PER_UPLOAD = 20
MAX_IMAGE_MB = 25
MAX_VIDEO_MB = 300  # phase 1; we can increase later with upload_session



def build_id_photo_dropbox_name(insured, original_filename: str) -> str:
    """
    Returns: <full insured name>_<datetime>_תמונת זיהוי<ext>
    Example: "ישראל_כהן_20260206_093012_תמונת_זיהוי.jpg"
    """
    # Full name
    first = (getattr(insured, "first_name", "") or "").strip()
    last  = (getattr(insured, "last_name", "") or "").strip()
    full_name = (f"{first} {last}").strip() or f"insured_{getattr(insured, 'id', '')}"

    # Normalize: spaces -> underscores, remove filesystem-unfriendly chars
    full_name = re.sub(r"\s+", "_", full_name)
    full_name = re.sub(r'[\\/:*?"<>|]+', "", full_name)   # keep Hebrew, remove bad chars
    full_name = full_name.strip("._ ")                    # cleanup

    # Extension from original file
    ext = os.path.splitext(original_filename or "")[1].lower()
    if not ext:
        ext = ".jpg"  # safe default

    # Timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{full_name}_{ts}_תמונת_זיהוי{ext}"



def build_media_target_folder(
    insured: GilInsured,
    media_type: str,
    report_id: int | None = None,
    expense_id: int | None = None
) -> str | None:
    """
    Reuse your existing folder convention and append the media subfolder.
    For expenses: store under .../הוצאות/<report_id>/<expense_id>
    """
    base = build_dropbox_folder_path(
        insured.insurance, insured.claim_type,
        insured.last_name, insured.first_name,
        insured.id_number, insured.claim_number
    )
    if not base:
        return None

    sub = MEDIA_SUBFOLDERS.get(media_type)
    if not sub:
        return None

    folder = f"{base}/{sub}"

    # ✅ Expenses: keep neat structure
    if media_type == "expenses":
        if report_id:
            folder = f"{folder}/{int(report_id)}"
        if expense_id:
            folder = f"{folder}/{int(expense_id)}"

    return folder



def ensure_dropbox_folder(path: str):
    """
    Idempotent: creates folder if missing, ignores 'already exists' conflict.
    """
    try:
        dbx.files_create_folder_v2(path)
    except ApiError as e:
        if not (e.error.is_path() and e.error.get_path().is_conflict()):
            raise


def validate_media_file(file_storage, media_type: str):
    """
    Validates file extension and size according to media_type.
    Raises ValueError on invalid file.
    """
    filename = (file_storage.filename or "").strip()
    if not filename:
        raise ValueError("Missing filename")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    size_bytes = getattr(file_storage, "content_length", None)

    # ✅ expenses: images only
    if media_type == "expenses":
        allowed = ALLOWED_IMAGE_EXTS
        is_video = False
    else:
        is_video = (media_type == "video")
        allowed = ALLOWED_VIDEO_EXTS if is_video else ALLOWED_IMAGE_EXTS.union(ALLOWED_VIDEO_EXTS)

    if ext not in allowed:
        raise ValueError(f"File type not allowed: {ext}")

    if size_bytes is not None:
        mb = size_bytes / (1024 * 1024)
        if is_video and mb > MAX_VIDEO_MB:
            raise ValueError(f"Video too large (>{MAX_VIDEO_MB}MB)")
        if (not is_video) and mb > MAX_IMAGE_MB:
            raise ValueError(f"Image too large (>{MAX_IMAGE_MB}MB)")



@main.route("/insured/<int:insured_id>/media/upload", methods=["POST"])
def insured_media_upload(insured_id: int):
    import os
    import json
    from datetime import datetime

    try:
        # session user (same pattern you use everywhere)
        user_data = session.get('user')
        user = json.loads(user_data) if user_data else {}
        if not user:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        insured = GilInsured.query.get_or_404(insured_id)

        media_type = (request.form.get("media_type") or "").strip()
        note = (request.form.get("note") or "").strip()

        if media_type not in ALLOWED_MEDIA_TYPES:
            return jsonify({"status": "error", "message": "Invalid media_type"}), 400

        # ----------------------------
        # form int helper
        # ----------------------------
        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return None

        # ✅ NEW: for expenses we expect report_id + expense_id
        report_id = _to_int(request.form.get("report_id"))
        expense_id = _to_int(request.form.get("expense_id"))

        if media_type == "expenses":
            if not report_id or not expense_id:
                return jsonify({"status": "error", "message": "report_id/expense_id required for expenses"}), 400

            # Validate expense belongs to this report + insured (no cross-case uploads)
            exp = GilTrackingExpense.query.get_or_404(expense_id)
            if exp.report_id != report_id:
                return jsonify({"status": "error", "message": "expense_id does not match report_id"}), 400

            rep = GilTrackingReport.query.get_or_404(report_id)
            if rep.insured_id != insured_id:
                return jsonify({"status": "error", "message": "report does not belong to insured"}), 400

        files = request.files.getlist("files")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        # ✅ expenses: only 1 invoice image per expense
        if media_type == "expenses" and len(files) != 1:
            return jsonify({"status": "error", "message": "Expenses require exactly 1 image file"}), 400

        if len(files) > MAX_FILES_PER_UPLOAD:
            return jsonify({"status": "error", "message": f"Too many files (max {MAX_FILES_PER_UPLOAD})"}), 400

        folder_path = build_media_target_folder(insured, media_type, report_id=report_id, expense_id=expense_id)
        if not folder_path:
            return jsonify({
                "status": "error",
                "message": "Cannot determine Dropbox folder. Check insured insurance/type fields."
            }), 400

        # Ensure the subfolder exists (safe if already exists)
        ensure_dropbox_folder(folder_path)

        results = []

        for f in files:
            try:
                validate_media_file(f, media_type)

                original_name = getattr(f, "filename", "") or "file"

                # Read bytes ONCE (used for size + upload + EXIF)
                data = f.read() or b""
                size_bytes = len(data)

                # size guard even if content_length not available
                mb = size_bytes / (1024 * 1024)
                if media_type == "video" and mb > MAX_VIDEO_MB:
                    raise ValueError(f"Video too large (>{MAX_VIDEO_MB}MB)")
                if media_type != "video" and mb > MAX_IMAGE_MB:
                    raise ValueError(f"Image too large (>{MAX_IMAGE_MB}MB)")

                # Expenses: stable name + overwrite
                if media_type == "expenses":
                    ext = os.path.splitext(original_name)[1].lower() or ".jpg"
                    stored_name = f"expense_{expense_id}{ext}"
                    write_mode = dropbox.files.WriteMode.overwrite
                else:
                    # Existing naming (keep as-is)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = secure_filename(original_name)

                    if media_type == "id_photo":
                        stored_name = build_id_photo_dropbox_name(insured, original_name)
                    else:
                        stored_name = f"{insured_id}_{ts}_{safe_name}"

                    write_mode = dropbox.files.WriteMode.add

                dropbox_path = f"{folder_path}/{stored_name}"

                dbx.files_upload(
                    data,
                    dropbox_path,
                    mode=write_mode,
                    mute=True
                )

                # ---------------------------------------------------------
                # ✅ Catalog uploaded media in gil_media (non-expenses)
                # ---------------------------------------------------------
                if media_type != "expenses":
                    taken_at = None

                    # Only try EXIF for image-based media
                    if media_type in ("photos", "id_photo"):
                        try:
                            taken_at = _extract_taken_at_from_exif_bytes(data)
                        except Exception:
                            taken_at = None

                    # If EXIF missing, fallback to now (UTC)
                    if not taken_at:
                        taken_at = datetime.utcnow()

                    upsert_gil_media(
                        insured_id=insured_id,
                        media_type=media_type,          # ✅ store UI value directly
                        dropbox_path=dropbox_path,
                        file_name=stored_name,
                        uploaded_by_user_id=(user.get("id") or None),
                        taken_at=taken_at,
                        note=note
                    )

                # ✅ expenses -> persist media row (1 per expense)
                if media_type == "expenses":
                    GilTrackingExpenseMedia.query.filter_by(expense_id=expense_id).delete()

                    m = GilTrackingExpenseMedia(
                        expense_id=expense_id,
                        storage_provider="dropbox",
                        file_name=stored_name,
                        file_ext=os.path.splitext(stored_name)[1].lower(),
                        mime_type=(getattr(f, "mimetype", None) or "image/jpeg"),
                        file_size=size_bytes,
                        dropbox_path=dropbox_path,
                        dropbox_file_id=None,
                        shared_url=None,
                        thumb_url=None
                    )
                    db.session.add(m)
                    db.session.commit()

                results.append({
                    "file": original_name,
                    "stored_name": stored_name,
                    "status": "success",
                    "dropbox_path": dropbox_path,
                    "size_bytes": size_bytes
                })

            except Exception as e:
                db.session.rollback()
                current_app.logger.exception("insured_media_upload file failed")
                results.append({
                    "file": getattr(f, "filename", "file"),
                    "status": "error",
                    "message": str(e)
                })

        return jsonify({
            "status": "success",
            "folder_path": folder_path,
            "note": note,
            "results": results
        })

    except Exception:
        current_app.logger.exception("insured_media_upload error")
        return jsonify({"status": "error", "message": "Server error"}), 500






@main.route("/insured/<int:insured_id>/media/list", methods=["GET"])
def insured_media_list(insured_id: int):
    try:
        # session user (same pattern you use everywhere)
        user_data = session.get('user')
        user = json.loads(user_data) if user_data else {}
        if not user:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        insured = GilInsured.query.get_or_404(insured_id)

        media_type = (request.args.get("media_type") or "").strip()
        if media_type not in ALLOWED_MEDIA_TYPES:
            return jsonify({"status": "error", "message": "Invalid media_type"}), 400

        folder_path = build_media_target_folder(insured, media_type)
        if not folder_path:
            return jsonify({
                "status": "error",
                "message": "Cannot determine Dropbox folder. Check insured insurance/type fields."
            }), 400

        # List folder in Dropbox
        files_out = []
        try:
            res = dbx.files_list_folder(folder_path)
            entries = list(res.entries)
            while res.has_more:
                res = dbx.files_list_folder_continue(res.cursor)
                entries.extend(res.entries)
        except ApiError:
            # folder might not exist yet -> return empty list (don’t error)
            return jsonify({"status": "success", "files": []})

        def guess_mime(name: str) -> str:
            n = (name or "").lower()
            if n.endswith((".jpg", ".jpeg")): return "image/jpeg"
            if n.endswith(".png"): return "image/png"
            if n.endswith(".webp"): return "image/webp"
            if n.endswith(".mp4"): return "video/mp4"
            if n.endswith(".mov"): return "video/quicktime"
            if n.endswith(".m4v"): return "video/x-m4v"
            if n.endswith(".avi"): return "video/x-msvideo"
            return "application/octet-stream"

        # Build temporary links for files
        for e in entries:
            # FileMetadata only (ignore subfolders)
            if not hasattr(e, "path_lower") or not hasattr(e, "name"):
                continue
            try:
                link = dbx.files_get_temporary_link(e.path_lower).link
            except ApiError:
                continue

            files_out.append({
                "name": e.name,
                "url": link,
                "mime_type": guess_mime(e.name)
            })

        return jsonify({"status": "success", "files": files_out})

    except Exception as e:
        current_app.logger.error(f"insured_media_list error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


@main.route("/api/tracking_expenses/<int:expense_id>/media/open", methods=["GET"])
def api_tracking_expense_media_open(expense_id: int):
    try:
        # session user
        user_data = session.get("user")
        user = json.loads(user_data) if user_data else {}
        if not user:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        exp = GilTrackingExpense.query.get_or_404(expense_id)
        rep = GilTrackingReport.query.get_or_404(exp.report_id)

        allowed, inv_row, _user = require_case_access_or_403(rep.insured_id, rep.ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        m = GilTrackingExpenseMedia.query.filter_by(expense_id=expense_id) \
            .order_by(GilTrackingExpenseMedia.media_id.desc()) \
            .first()

        if not m or not m.dropbox_path:
            return jsonify({"status": "error", "message": "No invoice uploaded"}), 404

        # Dropbox temporary link (no need to create shared links)
        tmp = dbx.files_get_temporary_link(m.dropbox_path)

        return jsonify({"status": "success", "url": tmp.link, "file_name": m.file_name or ""})

    except Exception as e:
        current_app.logger.error(f"api_tracking_expense_media_open error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


###################  Automate Media Upload ######################

from datetime import datetime
from PIL import Image, ExifTags
import os

def _extract_taken_at_from_exif(file_storage) -> datetime | None:
    """
    Reads EXIF DateTimeOriginal / DateTimeDigitized / DateTime.
    Returns datetime or None.
    """
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)

        exif = getattr(img, "_getexif", None)
        if not exif:
            return None

        exif_data = exif() or {}
        # map tag numbers to names
        tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}

        # EXIF formats: "YYYY:MM:DD HH:MM:SS"
        for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            v = tag_map.get(key)
            if v:
                try:
                    return datetime.strptime(v, "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass
        return None
    except Exception:
        return None
    finally:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass


def upsert_gil_media(
    insured_id: int,
    media_type: str,
    dropbox_path: str,
    file_name: str | None,
    uploaded_by_user_id: int | None,
    taken_at: datetime | None,
    note: str | None = None,
):
    """
    Insert new media row. If same dropbox_path already exists, update taken_at/taken_date/note.
    """
    taken_date = taken_at.date() if taken_at else None

    row = GilMedia.query.filter_by(dropbox_path=dropbox_path).first()
    if row:
        row.insured_id = insured_id
        row.media_type = media_type
        row.file_name = file_name
        row.taken_at = taken_at or row.taken_at
        row.taken_date = taken_date or row.taken_date
        row.uploaded_by_user_id = uploaded_by_user_id or row.uploaded_by_user_id
        if note:
            row.note = note
    else:
        row = GilMedia(
            insured_id=insured_id,
            media_type=media_type,
            dropbox_path=dropbox_path,
            file_name=file_name,
            taken_at=taken_at,
            taken_date=taken_date,
            uploaded_by_user_id=uploaded_by_user_id,
            note=note
        )
        db.session.add(row)

    db.session.commit()
    return row.media_id


@main.route("/reports/api/insured/<int:insured_id>/dropbox/photos-count", methods=["GET"])
def api_dropbox_photos_count_for_date(insured_id: int):
    """
    Baby step #1:
    Given insured_id + ref_number + date (ISO or dd/mm/yyyy),
    go to Dropbox folder .../תמונות and count how many photos match the date.

    Matching rule (fast + reliable):
    - We match filename containing YYYY-MM-DD (like your screenshot).
    - Counts only image extensions: jpg/jpeg/png/heic/webp.
    """
    try:
        ref_number = (request.args.get("ref_number") or "").strip()
        date_in = (request.args.get("date") or "").strip()

        if not ref_number:
            return jsonify({"status": "error", "message": "ref_number missing"}), 400
        if not date_in:
            return jsonify({"status": "error", "message": "date missing"}), 400

        # access control (same pattern you use)
        allowed, inv_row, user = require_case_access_or_403(int(insured_id), ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        insured = GilInsured.query.get_or_404(insured_id)

        # parse date (accept YYYY-MM-DD OR dd/mm/yyyy)
        d = parse_date_flexible(date_in)
        if not d:
            return jsonify({"status": "error", "message": "Invalid date"}), 400

        iso = d.strftime("%Y-%m-%d")
        dmy = d.strftime("%d/%m/%Y")

        base_path = build_dropbox_folder_path(
            insured.insurance, insured.claim_type,
            insured.last_name, insured.first_name,
            insured.id_number, insured.claim_number
        )
        if not base_path:
            return jsonify({"status": "ok", "count": 0, "date_iso": iso, "date_dmy": dmy, "folder": None})

        photos_folder = f"{base_path}/תמונות"

        exts = (".jpg", ".jpeg", ".png", ".heic", ".webp")
        count = 0

        try:
            res = dbx.files_list_folder(photos_folder)
            while True:
                for entry in res.entries:
                    # files only
                    if not hasattr(entry, "name"):
                        continue
                    name = (entry.name or "").lower()
                    if not name.endswith(exts):
                        continue
                    # match date in filename (your naming already includes YYYY-MM-DD)
                    if iso in name:
                        count += 1

                if not res.has_more:
                    break
                res = dbx.files_list_folder_continue(res.cursor)

        except ApiError as e:
            # folder might not exist yet -> treat as 0 photos (not a hard error)
            # (If you prefer strict behavior, return error instead)
            return jsonify({
                "status": "ok",
                "count": 0,
                "date_iso": iso,
                "date_dmy": dmy,
                "folder": photos_folder,
                "note": "Folder not found or not accessible"
            })

        return jsonify({
            "status": "ok",
            "count": count,
            "date_iso": iso,
            "date_dmy": dmy,
            "folder": photos_folder
        })

    except Exception as e:
        current_app.logger.error(f"api_dropbox_photos_count_for_date error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


@main.route("/reports/api/tracking_reports/<int:report_id>/media/import-from-dropbox", methods=["POST"])
def api_tracking_report_import_media_from_dropbox(report_id: int):
    """
    Baby step #2:
    Import photos from insured Dropbox folder (/תמונות) for selected tracking date
    into:
      - gil_media (upsert by insured_id + dropbox_path)
      - gil_tracking_report_media (link to report, unique prevents duplicates)

    IMPORTANT:
    The <report_id> in the URL might NOT be a GilTrackingReport id (editor save_draft id, etc.).
    So we fallback to locate/create the tracking report by (insured_id, ref_number, report_date).
    """
    try:
        from datetime import datetime
        from sqlalchemy import func
        from dropbox.exceptions import ApiError
        from werkzeug.exceptions import NotFound

        payload = request.get_json(silent=True) or {}

        insured_id = payload.get("insured_id")
        ref_number = (payload.get("ref_number") or "").strip()
        date_in    = (payload.get("date") or "").strip()

        if not insured_id or not ref_number or not date_in:
            return jsonify({"status": "error", "message": "insured_id/ref_number/date missing"}), 400

        # access control
        allowed, inv_row, user = require_case_access_or_403(int(insured_id), ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        # parse date
        d = parse_date_flexible(date_in)
        if not d:
            return jsonify({"status": "error", "message": "Invalid date"}), 400

        date_iso = d.strftime("%Y-%m-%d")
        date_dmy = d.strftime("%d/%m/%Y")

        # --- load insured (must exist) ---
        insured = GilInsured.query.get_or_404(int(insured_id))

        # --- Resolve tracking report safely ---
        r = GilTrackingReport.query.get(report_id)

        if not r:
            r = GilTrackingReport.query.filter_by(
                insured_id=int(insured_id),
                ref_number=ref_number,
                report_date=d
            ).first()

        # If still missing -> create tracking report draft now
        if not r:
            # Determine investigator_id
            investigator_id = None

            # If user is investigator, inv_row exists
            if inv_row:
                investigator_id = inv_row.id
            else:
                # admin flow: allow passing investigator_id (optional)
                investigator_id = payload.get("investigator_id")

                if not investigator_id:
                    # fallback to your existing helper if available
                    try:
                        inv2 = get_current_investigator_row()
                        if inv2:
                            investigator_id = inv2.id
                    except Exception:
                        investigator_id = None

            if not investigator_id:
                return jsonify({
                    "status": "error",
                    "message": "Cannot determine investigator_id for new tracking report (pass investigator_id or open as investigator)"
                }), 400

            r = GilTrackingReport(
                insured_id=int(insured_id),
                ref_number=ref_number,
                investigator_id=int(investigator_id),
                report_date=d,
                status="Draft",
                note="",
                mileage_km=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(r)
            db.session.flush()  # gets r.report_id

        # If report exists but belongs to different insured -> block
        if int(r.insured_id) != int(insured_id):
            return jsonify({"status": "error", "message": "Report/insured mismatch"}), 400

        # --- derive dropbox photos folder ---
        base_path = build_dropbox_folder_path(
            insured.insurance, insured.claim_type,
            insured.last_name, insured.first_name,
            insured.id_number, insured.claim_number
        )
        if not base_path:
            return jsonify({"status": "error", "message": "Cannot build Dropbox path"}), 400

        photos_folder = f"{base_path}/תמונות"

        allowed_exts = (".jpg", ".jpeg", ".png", ".heic", ".webp")

        # For sort_order, append after current max
        current_max_sort = db.session.query(func.max(GilTrackingReportMedia.sort_order)) \
            .filter(GilTrackingReportMedia.tracking_report_id == r.report_id) \
            .scalar()
        next_sort = int(current_max_sort or 0) + 1

        user_id = (user or {}).get("id") or None

        # list dropbox folder (paged)
        entries = []
        try:
            res = dbx.files_list_folder(photos_folder)
            while True:
                entries.extend(res.entries)
                if not res.has_more:
                    break
                res = dbx.files_list_folder_continue(res.cursor)
        except ApiError:
            return jsonify({
                "status": "error",
                "message": "Dropbox folder not accessible",
                "folder": photos_folder
            }), 400

        files_scanned = 0
        matched_files = []

        for entry in entries:
            if not hasattr(entry, "name"):
                continue

            name = (entry.name or "")
            low = name.lower()

            if not low.endswith(allowed_exts):
                continue

            files_scanned += 1

            # Match by date in filename (your naming includes YYYY-MM-DD)
            if date_iso not in low:
                continue

            dropbox_path = getattr(entry, "path_display", None) or getattr(entry, "path_lower", None)
            if not dropbox_path:
                continue

            matched_files.append({
                "file_name": name,
                "dropbox_path": dropbox_path
            })

        imported_count = 0
        linked_count = 0
        already_linked_count = 0
        media_out = []

        for f in matched_files:
            file_name = f["file_name"]
            dropbox_path = f["dropbox_path"]

            media_row = GilMedia.query.filter_by(
                insured_id=int(insured_id),
                dropbox_path=dropbox_path
            ).first()

            if not media_row:
                media_row = GilMedia(
                    insured_id=int(insured_id),
                    media_type="photo",
                    dropbox_path=dropbox_path,
                    file_name=file_name,
                    taken_date=d,
                    uploaded_by_user_id=user_id,
                    uploaded_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(media_row)
                db.session.flush()
                imported_count += 1
            else:
                media_row.file_name = media_row.file_name or file_name
                media_row.taken_date = media_row.taken_date or d
                media_row.updated_at = datetime.utcnow()

            existing_link = GilTrackingReportMedia.query.filter_by(
                tracking_report_id=r.report_id,
                media_id=media_row.media_id
            ).first()

            if existing_link:
                already_linked_count += 1
            else:
                link = GilTrackingReportMedia(
                    tracking_report_id=r.report_id,
                    media_id=media_row.media_id,
                    tag=None,
                    sort_order=next_sort,
                    created_by_user_id=user_id,
                    created_at=datetime.utcnow()
                )
                db.session.add(link)
                linked_count += 1
                next_sort += 1

            media_out.append({
                "media_id": media_row.media_id,
                "file_name": media_row.file_name or file_name,
                "dropbox_path": media_row.dropbox_path,
                "taken_date": normalize_date(media_row.taken_date),
            })

        db.session.commit()

        return jsonify({
            "status": "success",
            "tracking_report_id": r.report_id,
            "insured_id": int(insured_id),
            "date_iso": date_iso,
            "date_dmy": date_dmy,
            "folder": photos_folder,
            "files_scanned": files_scanned,
            "matched_count": len(matched_files),
            "imported_count": imported_count,
            "linked_count": linked_count,
            "already_linked_count": already_linked_count,
            "media": media_out
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"api_tracking_report_import_media_from_dropbox error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500



def build_dropbox_folder_for_insured(insured_id: int) -> str:
    """
    Builds the insured Dropbox base folder path (WITHOUT /תמונות).
    """
    insured = GilInsured.query.get_or_404(insured_id)

    insurance_company = (
        getattr(insured, "insurance_company", None)
        or getattr(insured, "insurance", None)
        or getattr(insured, "insurance_name", None)
        or ""
    )

    claim_type = (
        getattr(insured, "claim_type", None)
        or getattr(insured, "injury_type", None)
        or getattr(insured, "case_type", None)
        or ""
    )

    first_name = getattr(insured, "first_name", None) or ""
    last_name  = getattr(insured, "last_name", None) or ""

    if not (first_name or last_name):
        full_name = (
            getattr(insured, "full_name", None)
            or getattr(insured, "name", None)
            or ""
        ).strip()
        parts = full_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = " ".join(parts[1:])
        else:
            last_name = full_name

    id_number = (
        str(getattr(insured, "id_number", None) or "")
        or str(getattr(insured, "tz", None) or "")
        or ""
    ).strip()

    claim_number = (
        str(getattr(insured, "claim_number", None) or "")
        or str(getattr(insured, "claim_no", None) or "")
        or ""
    ).strip()

    return build_dropbox_folder_path(
        insurance_company,
        claim_type,
        last_name,
        first_name,
        id_number,
        claim_number
    )


@main.route("/reports/api/insured/<int:insured_id>/dropbox/list-photos", methods=["GET"])
def api_list_dropbox_photos(insured_id: int):
    """
    List photo files from the insured Dropbox folder (/תמונות) for a given YYYY-MM-DD date.
    Returns temporary links for client preview,
    AND upserts each file into GilMedia so reports_docx.resolve_one() can download on-demand.
    """
    try:
        # (optional) ref_number used for access check if provided
        ref_number = (request.args.get("ref_number") or "").strip()
        user = require_case_access_or_403(ref_number, session) if ref_number else None
        user_id = (user or {}).get("id") or 0

        date_iso = (request.args.get("date") or "").strip()  # YYYY-MM-DD
        if not date_iso:
            return jsonify({"status": "error", "message": "Missing date"}), 400

        # ✅ Build insured base folder, then go into /תמונות
        base_folder = build_dropbox_folder_for_insured(insured_id)
        photos_folder = f"{base_folder}/תמונות"

        # list folder (paged)
        try:
            res = dbx.files_list_folder(photos_folder)
        except Exception:
            # folder may not exist yet
            return jsonify({"status": "ok", "count": 0, "files": [], "folder": photos_folder})

        entries = list(res.entries)
        while res.has_more:
            res = dbx.files_list_folder_continue(res.cursor)
            entries.extend(res.entries)

        # keep only image files that contain the requested date in the filename
        exts = (".jpg", ".jpeg", ".png", ".webp", ".heic")
        matched = []
        for e in entries:
            name = getattr(e, "name", "") or ""
            if not name:
                continue
            low = name.lower()
            if low.endswith(exts) and (date_iso in low):
                matched.append(e)

        def guess_mime(name: str) -> str:
            n = (name or "").lower()
            if n.endswith(".png"):
                return "image/png"
            if n.endswith(".webp"):
                return "image/webp"
            if n.endswith(".heic"):
                return "image/heic"
            return "image/jpeg"

        files_out = []

        # ✅ Upsert into GilMedia so resolve_one(base_name) works later
        for e in matched:
            dropbox_path = getattr(e, "path_lower", None)
            if not dropbox_path:
                continue

            # temp link for UI preview
            try:
                tmp = dbx.files_get_temporary_link(dropbox_path)
                url = tmp.link
            except Exception:
                url = None

            try:
                # Prefer your helper if it exists
                if "upsert_gil_media" in globals() and callable(globals()["upsert_gil_media"]):
                    upsert_gil_media(
                        insured_id=insured_id,
                        media_type="photo",
                        file_name=e.name,
                        dropbox_path=dropbox_path,
                        uploaded_by_user_id=user_id,
                        taken_at=None,
                        note="dropbox-cloud",
                    )
                else:
                    # fallback: upsert by (insured_id, file_name)
                    row = (
                        GilMedia.query
                        .filter_by(insured_id=insured_id, file_name=e.name)
                        .order_by(GilMedia.media_id.desc())
                        .first()
                    )
                    if row:
                        if hasattr(row, "dropbox_path"):
                            row.dropbox_path = dropbox_path
                        if hasattr(row, "media_type"):
                            row.media_type = "photo"
                        if hasattr(row, "note") and not row.note:
                            row.note = "dropbox-cloud"
                    else:
                        kwargs = {}
                        if hasattr(GilMedia, "insured_id"): kwargs["insured_id"] = insured_id
                        if hasattr(GilMedia, "media_type"): kwargs["media_type"] = "photo"
                        if hasattr(GilMedia, "file_name"):  kwargs["file_name"] = e.name
                        if hasattr(GilMedia, "dropbox_path"): kwargs["dropbox_path"] = dropbox_path
                        if hasattr(GilMedia, "uploaded_by_user_id"): kwargs["uploaded_by_user_id"] = user_id
                        if hasattr(GilMedia, "note"): kwargs["note"] = "dropbox-cloud"
                        db.session.add(GilMedia(**kwargs))

                    db.session.commit()

            except Exception as ex:
                db.session.rollback()
                current_app.logger.warning(
                    "[DROPBOX][list-photos] GilMedia upsert failed for %s: %s",
                    e.name, ex
                )

            files_out.append({
                "name": e.name,
                "mime": guess_mime(e.name),
                "url": url,
                "dropbox_path": dropbox_path,
            })

        files_out.sort(key=lambda x: x.get("name") or "")

        return jsonify({
            "status": "ok",
            "count": len(files_out),
            "files": files_out,
            "folder": photos_folder
        })

    except Exception as e:
        current_app.logger.exception("[DROPBOX][list-photos] failed: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500



@main.route("/investigator_dashboard", methods=["GET"])
def investigator_dashboard():
    # Must be logged in
    user_data = session.get("user")
    if not user_data:
        return redirect(url_for("main.login"))

    user = json.loads(user_data)

    # Investigators only
    if user.get("role") != "Investigator":
        return redirect(url_for("main.login"))

    # Keep same roles pattern used everywhere
    roles = TocRole.query.all()
    roles_list = [{"role": r.role, "exclusions": r.exclusions} for r in roles]

    # UI-only page (hard-coded metrics in the template for now)
    return render_template(
        "investigator_dashboard.html",
        user=user,
        roles=roles_list
    )

@main.route("/investigator_cases", methods=["GET"])
def investigator_cases():
    return render_template("investigator_cases.html")


@main.route("/investigator/insured/<int:id>")
def investigator_insured(id):
    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}

    if not user or user.get("role") != "Investigator":
        return redirect(url_for("main.login"))

    # Real data
    insured = GilInsured.query.get_or_404(id)

    # Lists used in insured.html (even if we render read-only)
    clinics = GilClinics.query.all()
    koopa = GilKoopa.query.all()

    # roles (keeps your base pattern consistent)
    roles = db.session.query(TocRole).all()
    roles_list = [{"role": r.role, "exclusions": r.exclusions} for r in roles]

    return render_template(
        "investigator_insured.html",
        user=user,
        roles=roles_list,
        insured=insured,
        clinics=clinics,
        koopa=koopa,
    )

# ==========================================
# Investigator Tasks API
# ==========================================

@main.route("/api/investigator/tasks/summary")
def investigator_tasks_summary():
    user_data = session.get("user")
    if not user_data:
        return jsonify({"error": "Unauthorized"}), 401

    user = json.loads(user_data)
    investigator = GilInvestigator.query.filter_by(user_id=user["id"]).first()
    if not investigator:
        return jsonify({"error": "No investigator profile"}), 403

    today = date.today()

    open_statuses = ["פתוחה", "בתהליך"]

    open_count = GilTask.query.filter(
        GilTask.investigator_id == investigator.id,
        GilTask.status.in_(open_statuses)
    ).count()

    overdue_count = GilTask.query.filter(
        GilTask.investigator_id == investigator.id,
        GilTask.status.in_(open_statuses),
        GilTask.due_date != None,
        GilTask.due_date < today
    ).count()

    return jsonify({
        "open_count": open_count,
        "overdue_count": overdue_count
    })


from sqlalchemy import case

@main.route("/api/investigator/tasks/recent")
def investigator_tasks_recent():
    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    investigator = GilInvestigator.query.filter_by(user_id=user.get("id")).first()
    if not investigator:
        return jsonify([])

    # toggle param from frontend
    show_all = (request.args.get("show_all", "0") == "1")

    default_statuses = ["פתוחה", "חדש", "בתהליך"]

    # Base query
    q = (
        db.session.query(GilTask, GilInsured)
        .outerjoin(GilInsured, GilInsured.id == GilTask.case_id)
        .filter(GilTask.investigator_id == investigator.id)
    )

    # Apply status filter only when NOT show_all
    if not show_all:
        q = q.filter(GilTask.status.in_(default_statuses))

    tasks = (
        q.order_by(
            case(
                (GilTask.status == "הושלמה", 1),
                else_=0
            ),  # completed last
            GilTask.due_date.is_(None),      # NULL due_date last (MySQL safe)
            GilTask.due_date.asc(),
            GilTask.date_created.desc()
        )
        .limit(5)
        .all()
    )

    out = []
    for task, insured in tasks:
        insured_name = None
        case_ref = None

        if insured:
            first = (insured.first_name or "").strip()
            last  = (insured.last_name or "").strip()
            insured_name = f"{first} {last}".strip() or None
            case_ref = (getattr(insured, "ref_number", None) or "").strip() or None

        out.append({
            "id": task.id,
            "case_id": task.case_id,
            "title": task.title,
            "description": task.description or "",
            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "status": task.status or "",
            "insured_name": insured_name,
            "case_ref": case_ref,
        })

    return jsonify(out)




@main.route("/api/investigator/tasks/<int:task_id>/accept", methods=["POST"])
def investigator_accept_task(task_id):
    user_data = session.get("user")
    if not user_data:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    user = json.loads(user_data)

    investigator = GilInvestigator.query.filter_by(user_id=user["id"]).first()
    if not investigator:
        return jsonify({"status": "error", "message": "No investigator profile"}), 403

    task = GilTask.query.get_or_404(task_id)

    # Security: investigator can accept only their own task
    if task.investigator_id != investigator.id:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    # Only accept if currently open
    if task.status not in ("פתוחה", "חדש"):
        return jsonify({"status": "error", "message": "Task not open"}), 400

    task.status = "בתהליך"
    db.session.commit()

    return jsonify({"status": "success", "task_id": task.id, "new_status": task.status})


@main.route("/api/investigator/tasks/<int:task_id>/complete", methods=["POST"])
def investigator_complete_task(task_id):
    user_data = session.get("user")
    if not user_data:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    user = json.loads(user_data)

    investigator = GilInvestigator.query.filter_by(user_id=user["id"]).first()
    if not investigator:
        return jsonify({"status": "error", "message": "No investigator profile"}), 403

    task = GilTask.query.get_or_404(task_id)

    # Security: investigator can complete only their own task
    if task.investigator_id != investigator.id:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    # Only complete if currently in progress (prevents completing "חדש" without accepting)
    if task.status != "בתהליך":
        return jsonify({"status": "error", "message": "Task not in progress"}), 400

    task.status = "הושלמה"
    db.session.commit()

    return jsonify({"status": "success", "task_id": task.id, "new_status": task.status})

##################### Investigator Calendar #######################



@main.route("/investigator/calendar", methods=["GET"])
def investigator_calendar():

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}

    if not user:
        return redirect(url_for("main.login"))

    return render_template("investigator_calendar.html", user=user)



def _combine_date_time(d, t):
    """
    d: date or 'YYYY-MM-DD'
    t: datetime.time OR timedelta (common from MySQL TIME) OR string 'HH:MM'/'HH:MM:SS'
    returns ISO string 'YYYY-MM-DDTHH:MM:SS'
    """
    if d is None:
        return None

    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()

    if t is None:
        return datetime.combine(d, time(0, 0, 0)).isoformat()

    # MySQL TIME often arrives as timedelta
    if isinstance(t, timedelta):
        total_seconds = int(t.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        h = (total_seconds // 3600) % 24
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        t = time(h, m, s)

    if isinstance(t, str):
        s = t.strip()
        fmt = "%H:%M:%S" if len(s) == 8 else "%H:%M"
        t = datetime.strptime(s, fmt).time()

    # already datetime.time => ok
    return datetime.combine(d, t).isoformat()




@main.route("/api/investigator/calendar/events", methods=["GET"])
def api_investigator_calendar_events():
    """
    Returns FullCalendar events for the logged-in investigator.
    Pulls from:
      - gil_appointments
      - gil_investigator_appointments (assignment table)
      - gil_insured (for ref_number + name)
    """

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    inv_row = get_current_investigator_row()
    if not inv_row:
        return jsonify({"status": "error", "message": "Investigator not found for this user"}), 400

    investigator_id = inv_row.id
    if not investigator_id:
        return jsonify({"status": "error", "message": "Missing investigator_id in session"}), 400

    # FullCalendar passes start/end as ISO strings
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    start_date = None
    end_date = None
    try:
        if start:
            start_date = datetime.fromisoformat(start.replace("Z", "+00:00")).date()
        if end:
            end_date = datetime.fromisoformat(end.replace("Z", "+00:00")).date()
    except Exception:
        start_date = None
        end_date = None

    # ✅ Join gil_insured to get ref_number + names
    sql = """
        SELECT
            a.id,
            a.case_id,
            a.status,
            a.appointment_date,
            a.time_from,
            a.time_to,
            a.address,
            a.place,
            a.doctor,
            a.koopa,
            a.notes,
            ins.ref_number       AS ref_number,
            ins.first_name       AS insured_first_name,
            ins.last_name        AS insured_last_name
        FROM gil_appointments a
        JOIN gil_investigator_appointments ia
          ON ia.appointment_id = a.id
        LEFT JOIN gil_insured ins
          ON ins.id = a.case_id
        WHERE ia.investigator_id = :investigator_id
    """

    params = {"investigator_id": investigator_id}

    if start_date and end_date:
        sql += " AND a.appointment_date >= :start_date AND a.appointment_date < :end_date "
        params["start_date"] = start_date
        params["end_date"] = end_date

    sql += " ORDER BY a.appointment_date ASC, a.time_from ASC "

    rows = db.session.execute(text(sql), params).mappings().all()

    events = []
    for r in rows:
        appt_date = r["appointment_date"]
        time_from = r["time_from"]
        time_to = r["time_to"]

        start_iso = _combine_date_time(appt_date, time_from)
        end_iso = _combine_date_time(appt_date, time_to) if time_to else None

        # ✅ Event title should be the "event title" only (place/address)
        # so dashboard can show: ref_number - full_name - <title>
        title = (r["place"] or r["address"] or "אירוע").strip()

        status = (r["status"] or "").strip()
        color = None
        if status in ("נוצר", "חדש", "פתוח"):
            color = "#0d6efd"
        elif status in ("בתהליך", "מאושר"):
            color = "#198754"
        elif status in ("בוטל", "ביטול", "סגור"):
            color = "#dc3545"

        first_name = (r["insured_first_name"] or "").strip()
        last_name = (r["insured_last_name"] or "").strip()
        insured_name = f"{first_name} {last_name}".strip()

        events.append({
            "id": f"appt-{r['id']}",
            "title": title,
            "start": start_iso,
            "end": end_iso,
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {
                "appointment_id": r["id"],
                "case_id": r["case_id"],

                # ✅ what you need for dashboard title:
                "case_ref": r["ref_number"] or "",
                "insured_name": insured_name,

                "status": status,
                "address": r["address"],
                "place": r["place"],
                "doctor": r["doctor"],
                "koopa": r["koopa"],
                "notes": r["notes"],
            }
        })

    return jsonify(events)


@main.route("/api/investigator/appointments/<int:appointment_id>/json", methods=["GET"])
def api_investigator_appointment_json(appointment_id: int):
    """
    Investigator-only: returns a single appointment JSON
    ONLY if this appointment is assigned to the logged-in investigator.
    """

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    inv_row = get_current_investigator_row()
    if not inv_row:
        return jsonify({"status": "error", "message": "Investigator not found for this user"}), 400

    investigator_id = inv_row.id
    if not investigator_id:
        return jsonify({"status": "error", "message": "Missing investigator_id in session"}), 400

    # Must be assigned to this investigator
    assigned = GilInvestigatorAppointment.query.filter_by(
        appointment_id=appointment_id,
        investigator_id=investigator_id
    ).first()

    if not assigned:
        return jsonify({"status": "error", "message": "Not authorized"}), 403

    appt = GilAppointment.query.get_or_404(appointment_id)

    inv_links = GilInvestigatorAppointment.query.filter_by(appointment_id=appt.id).all()
    investigator_ids = [link.investigator_id for link in inv_links]
    investigator_names = [link.investigator.full_name for link in inv_links if link.investigator]

    data = {
        "id": appt.id,
        "case_id": appt.case_id,
        "appointment_date": appt.appointment_date.isoformat() if appt.appointment_date else "",
        "time_from": normalize_time(appt.time_from),
        "time_to": normalize_time(appt.time_to),
        "status": appt.status or "",
        "place": appt.place or "",
        "doctor": appt.doctor or "",
        "koopa": appt.koopa or "",
        "address": appt.address or "",
        "notes": appt.notes or "",
        "investigator_ids": investigator_ids,
        "investigators": ", ".join(investigator_names)
    }
    return jsonify(data)

##################### Case notes #####################


##################### Case notes #####################

@main.route("/api/insured/<int:insured_id>/notes", methods=["GET", "POST"])
def api_insured_notes(insured_id: int):
    import json
    from datetime import datetime
    from flask import jsonify, session, request, current_app
    from app import db
    from .models import GilInsured, GilCaseNote

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    insured = GilInsured.query.get_or_404(insured_id)

    # =========================
    # GET: list notes + temp links
    # =========================
    if request.method == "GET":
        dbx = get_dbx()

        notes = (
            GilCaseNote.query
            .filter(GilCaseNote.insured_id == insured.id)
            .order_by(GilCaseNote.note_datetime.desc())
            .all()
        )

        data = []
        for n in notes:
            photos_payload = []
            for p in (n.photos or []):
                temp_link = None
                try:
                    temp_link = dbx.files_get_temporary_link(p.dropbox_path).link
                except Exception:
                    temp_link = None

                photos_payload.append({
                    "photo_id": p.photo_id,
                    "dropbox_path": p.dropbox_path,
                    "file_name": p.file_name,
                    "mime_type": p.mime_type,
                    "file_size": p.file_size,
                    "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                    "temp_link": temp_link,
                })

            data.append({
                "note_id": n.note_id,
                "insured_id": n.insured_id,
                "note_datetime": n.note_datetime.isoformat() if n.note_datetime else None,
                "note_text": n.note_text,
                "created_by_user_id": n.created_by_user_id,
                "created_by_name": (
                    f"{(n.created_by.first_name or '')} {(n.created_by.last_name or '')}".strip()
                    if n.created_by else ""
                ),
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
                "photos": photos_payload,
            })

        return jsonify({"status": "success", "notes": data})

    # =========================
    # POST: create note
    # =========================
    payload = request.get_json(silent=True) or {}
    note_text = (payload.get("note_text") or "").strip()
    note_datetime_raw = (payload.get("note_datetime") or "").strip()

    if not note_text:
        return jsonify({"status": "error", "message": "Note text is required"}), 400

    note_dt = None
    if note_datetime_raw:
        try:
            note_dt = datetime.fromisoformat(note_datetime_raw.replace("Z", "+00:00"))
        except Exception:
            return jsonify({"status": "error", "message": "Invalid datetime format"}), 400

    new_note = GilCaseNote(
        insured_id=insured.id,
        created_by_user_id=int(user.get("id")),
        note_datetime=note_dt or datetime.utcnow(),
        note_text=note_text
    )

    db.session.add(new_note)
    db.session.commit()

    return jsonify({"status": "success", "note_id": new_note.note_id})


@main.route("/api/notes/<int:note_id>", methods=["PUT"])
def api_update_note(note_id: int):
    import json
    from datetime import datetime
    from flask import jsonify, session, request
    from app import db
    from .models import GilCaseNote

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    note = GilCaseNote.query.get_or_404(note_id)

    payload = request.get_json(silent=True) or {}
    note_text = (payload.get("note_text") or "").strip()
    note_datetime_raw = (payload.get("note_datetime") or "").strip()

    if note_text:
        note.note_text = note_text

    if note_datetime_raw:
        try:
            note.note_datetime = datetime.fromisoformat(note_datetime_raw.replace("Z", "+00:00"))
        except Exception:
            return jsonify({"status": "error", "message": "Invalid datetime format"}), 400

    db.session.commit()
    return jsonify({"status": "success"})


@main.route("/api/notes/<int:note_id>", methods=["DELETE"])
def api_delete_note(note_id: int):
    import json
    from flask import jsonify, session, current_app
    from app import db
    from .models import GilCaseNote

    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    note = GilCaseNote.query.get_or_404(note_id)

    # delete photos in Dropbox (best effort)
    dbx = get_dbx()
    for p in (note.photos or []):
        try:
            if p.dropbox_path:
                dbx.files_delete_v2(p.dropbox_path)
        except Exception:
            pass

    db.session.delete(note)
    db.session.commit()

    return jsonify({"status": "success"})


@main.route("/api/notes/<int:note_id>/photos/upload", methods=["POST"])
def api_upload_note_photos(note_id: int):
    import os
    import json
    from datetime import datetime
    from flask import jsonify, request, session, current_app
    from werkzeug.utils import secure_filename
    import dropbox
    from app import db
    from .models import GilCaseNote, GilCaseNotePhoto

    try:
        user_data = session.get("user")
        user = json.loads(user_data) if user_data else {}
        if not user:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        note = GilCaseNote.query.get_or_404(note_id)
        insured_id = note.insured_id

        files = request.files.getlist("files")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        dbx = get_dbx()

        # ✅ Reuse your existing insured Dropbox base folder builder
        base_folder = build_dropbox_folder_for_insured(insured_id)

        # ✅ Required folder under insured directory
        notes_root = f"{base_folder}/הערות-תמונות"
        note_folder = f"{notes_root}/NOTE-{note.note_id}"

        ensure_dropbox_folder(notes_root)
        ensure_dropbox_folder(note_folder)

        created = []

        for f in files:
            if not f or not f.filename:
                continue

            original_name = f.filename
            safe_name = secure_filename(original_name) or "photo"
            content = f.read() or b""
            if not content:
                continue

            _, ext = os.path.splitext(safe_name)
            if not ext:
                ext = ".jpg"

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stored_name = f"{ts}_{safe_name}"
            dropbox_path = f"{note_folder}/{stored_name}"

            meta = dbx.files_upload(
                content,
                dropbox_path,
                mode=dropbox.files.WriteMode.add,
                autorename=True,
                mute=True
            )

            final_path = getattr(meta, "path_lower", None) or dropbox_path

            photo = GilCaseNotePhoto(
                note_id=note.note_id,
                dropbox_path=final_path,
                file_name=original_name,
                mime_type=(getattr(f, "mimetype", None) or None),
                file_size=len(content),
                uploaded_by_user_id=int(user.get("id")),
                uploaded_at=datetime.utcnow()
            )
            db.session.add(photo)
            created.append(photo)

        db.session.commit()
        return jsonify({"status": "success", "created": len(created)})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("api_upload_note_photos failed")
        return jsonify({"status": "error", "message": "Server error"}), 500


@main.route("/api/note-photos/<int:photo_id>", methods=["DELETE"])
def api_delete_note_photo(photo_id: int):
    import json
    from flask import jsonify, session, current_app
    from app import db
    from .models import GilCaseNotePhoto

    try:
        user_data = session.get("user")
        user = json.loads(user_data) if user_data else {}
        if not user:
            return jsonify({"status": "error", "message": "Not logged in"}), 401

        photo = GilCaseNotePhoto.query.get_or_404(photo_id)

        dbx = get_dbx()
        try:
            if photo.dropbox_path:
                dbx.files_delete_v2(photo.dropbox_path)
        except Exception:
            pass

        db.session.delete(photo)
        db.session.commit()
        return jsonify({"status": "success"})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("api_delete_note_photo failed")
        return jsonify({"status": "error", "message": "Server error"}), 500


if __name__ == '__main__':
    app.run(debug=True)





