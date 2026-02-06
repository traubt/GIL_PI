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
        return redirect(url_for('main.investigators'))
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
    user_data = session.get('user')
    user = json.loads(user_data)
    user_id = user["id"]
    user = User.query.get(user_id)

    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json()

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
        return jsonify({"success": False, "error": str(e)}), 500

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


@main.route('/tasks/<int:id>/json', methods=['GET'])
def get_task_json(id):
    task = GilTask.query.get_or_404(id)
    return jsonify({
        "id": task.id,
        "case_id": task.case_id,
        "title": task.title,
        "description": task.description or "",
        "due_date": str(task.due_date) if task.due_date else "",
        "status": task.status or "",
        "investigator_id": task.investigator_id
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


@main.route("/api/tracking_reports/<int:report_id>", methods=["GET"])
def api_tracking_report_get(report_id):
    try:
        r = GilTrackingReport.query.get_or_404(report_id)

        allowed, inv_row, user = require_case_access_or_403(r.insured_id, r.ref_number)
        if not allowed:
            return jsonify({"status": "error", "message": "Access denied"}), 403

        items = GilTrackingReportActivity.query.filter_by(report_id=r.report_id) \
            .order_by(GilTrackingReportActivity.sort_order.asc(), GilTrackingReportActivity.activity_id.asc()) \
            .all()

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
                "mileage_km": r.mileage_km,  # ✅ NEW
                "items": [{
                    "activity_id": it.activity_id,
                    "activity_time": normalize_time(it.activity_time),
                    "description": it.description or "",
                    "sort_order": int(it.sort_order or 0)
                } for it in items]
            }
        })

    except Exception as e:
        current_app.logger.error(f"api_tracking_report_get error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


@main.route("/api/tracking_reports/save", methods=["POST"])
def api_tracking_report_save():
    try:
        payload = request.get_json(silent=True) or {}

        insured_id = payload.get("insured_id")
        ref_number = (payload.get("ref_number") or "").strip()
        report_date_in = (payload.get("report_date") or "").strip()   # "YYYY-MM-DD" or "DD/MM/YYYY"
        note = (payload.get("note") or "").strip()
        items = payload.get("items") or []
        report_id = payload.get("report_id")  # optional

        # ✅ NEW: mileage
        mileage_in = payload.get("mileage_km", None)
        mileage_km = None
        try:
            # allow "", None => NULL
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

        # Determine investigator_id:
        # - Investigator user: must be inv_row.id
        # - Admin/Manager: can use payload investigator_id or keep existing
        investigator_id = None
        if user_is_admin_or_manager(user):
            investigator_id = payload.get("investigator_id")
        else:
            investigator_id = inv_row.id if inv_row else None

        if not investigator_id:
            return jsonify({"status": "error", "message": "investigator_id missing"}), 400

        # Load existing by report_id OR unique key (ref_number + report_date)
        r = None
        if report_id:
            r = GilTrackingReport.query.get(report_id)

        if not r:
            r = GilTrackingReport.query.filter_by(ref_number=ref_number, report_date=d).first()

        # ✅ If Final => cannot edit (server-side enforcement)
        if r and (r.status == "Final"):
            if not user_is_admin_or_manager(user):
                return jsonify({"status": "error", "message": "Report is Final and cannot be edited"}), 403

        if not r:
            r = GilTrackingReport(
                insured_id=int(insured_id),
                ref_number=ref_number,
                investigator_id=int(investigator_id),
                report_date=d,
                status="Draft",
                note=note,
                mileage_km=mileage_km  # ✅ NEW
            )
            db.session.add(r)
            db.session.flush()  # get r.report_id
        else:
            # If investigator (not admin), don't allow editing a report created by another investigator (optional rule)
            if (not user_is_admin_or_manager(user)) and (r.investigator_id != int(investigator_id)):
                return jsonify({"status": "error", "message": "Cannot edit another investigator's report"}), 403

            r.note = note
            r.mileage_km = mileage_km  # ✅ NEW
            r.updated_at = datetime.utcnow()

        # Replace activities (simple and reliable)
        GilTrackingReportActivity.query.filter_by(report_id=r.report_id).delete()

        # items: [{activity_time:"HH:MM", description:"...", sort_order:0}, ...]
        for idx, it in enumerate(items):
            t = (it.get("activity_time") or "").strip()
            desc = (it.get("description") or "").strip()
            if not t or not desc:
                continue

            t_parsed = parse_time(t)  # <-- reuse your existing global parse_time()
            if not t_parsed:
                continue

            sort_order = it.get("sort_order")
            if sort_order is None:
                sort_order = idx

            db.session.add(GilTrackingReportActivity(
                report_id=r.report_id,
                activity_time=t_parsed,
                description=desc,
                sort_order=int(sort_order)
            ))

        db.session.commit()

        return jsonify({
            "status": "success",
            "report_id": r.report_id,
            "report_date": normalize_date(r.report_date),
            "status_value": r.status or "Draft",
            "mileage_km": r.mileage_km  # ✅ optional but nice
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



def build_media_target_folder(insured: GilInsured, media_type: str) -> str | None:
    """
    Reuse your existing folder convention and just append the media subfolder.
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
    return f"{base}/{sub}"


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

    # content_length is sometimes None with multipart; we can still validate after reading
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

        files = request.files.getlist("files")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        if len(files) > MAX_FILES_PER_UPLOAD:
            return jsonify({"status": "error", "message": f"Too many files (max {MAX_FILES_PER_UPLOAD})"}), 400

        folder_path = build_media_target_folder(insured, media_type)
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

                # =========================================================
                # ✅ Item 3: ONLY for ID photo - rename on Dropbox
                # =========================================================
                if media_type == "id_photo":
                    # IMPORTANT: do NOT use secure_filename here because it strips Hebrew.
                    stored_name = build_id_photo_dropbox_name(insured, original_name)
                else:
                    # Existing naming (keep as-is)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = secure_filename(original_name)
                    stored_name = f"{insured_id}_{ts}_{safe_name}"

                dropbox_path = f"{folder_path}/{stored_name}"

                # Phase 1: direct upload (good for photos + moderate videos)
                data = f.read()
                size_bytes = len(data)

                # size guard even if content_length not available
                mb = size_bytes / (1024 * 1024)
                if media_type == "video" and mb > MAX_VIDEO_MB:
                    raise ValueError(f"Video too large (>{MAX_VIDEO_MB}MB)")
                if media_type != "video" and mb > MAX_IMAGE_MB:
                    raise ValueError(f"Image too large (>{MAX_IMAGE_MB}MB)")

                dbx.files_upload(
                    data,
                    dropbox_path,
                    mode=dropbox.files.WriteMode.add,
                    mute=True
                )

                results.append({
                    "file": original_name,
                    "stored_name": stored_name,   # ✅ helpful for debugging
                    "status": "success",
                    "dropbox_path": dropbox_path,
                    "size_bytes": size_bytes
                })

            except Exception as e:
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

    except Exception as e:
        current_app.logger.error(f"insured_media_upload error: {e}")
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



if __name__ == '__main__':
    app.run(debug=True)





