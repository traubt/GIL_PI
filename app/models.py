from email.policy import default

from . import db
from flask_sqlalchemy import SQLAlchemy
import datetime
from datetime import datetime,timezone


class User(db.Model):
    __tablename__ = 'toc_users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(45), nullable=True)
    password = db.Column(db.String(45), nullable=True)
    creation_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_date = db.Column(db.DateTime, nullable=True)
    first_name = db.Column(db.String(45), nullable=True)
    last_name = db.Column(db.String(45), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    shop = db.Column(db.String(45), nullable=True)
    role = db.Column(db.String(45), nullable=False, default='AGENT')
    company = db.Column(db.String(45), nullable=True)
    job = db.Column(db.String(45), nullable=True)
    phone = db.Column(db.String(45), nullable=True)
    about = db.Column(db.String(200), nullable=True)
    profile_image = db.Column(db.String(100), nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    city = db.Column(db.String(45), nullable=True)
    county = db.Column(db.String(45), nullable=True)
    loc = db.Column(db.String(45), nullable=True)
    postal = db.Column(db.String(45), nullable=True)
    region = db.Column(db.String(45), nullable=True)
    timezone = db.Column(db.String(45), nullable=True)
    country_code = db.Column(db.String(45), nullable=True)
    country_calling_code = db.Column(db.String(45), nullable=True)

class TOC_SHOPS(db.Model):
    __tablename__ = 'toc_shops'

    blName = db.Column(db.String(255), primary_key=True)
    blId = db.Column(db.BigInteger)
    country = db.Column(db.String(2))
    timezone = db.Column(db.String(50))
    store = db.Column(db.String(10))
    customer = db.Column(db.String(10))
    mt_shop_name = db.Column(db.String(50))
    actv_ind = db.Column(db.Integer)
    tier =  db.Column(db.String(2))
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    address = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    zip = db.Column(db.String(5))
    city  = db.Column(db.String(20))
    state = db.Column(db.String(20))

class TocMessages(db.Model):
    __tablename__ = 'toc_messages'

    msg_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    msg_date = db.Column(db.DateTime)
    msg_from = db.Column(db.String(45), nullable=True)
    msg_to = db.Column(db.String(45), nullable=True)
    msg_subject = db.Column(db.String(100), nullable=True)
    msg_body = db.Column(db.String(400), nullable=True)
    msg_status = db.Column(db.String(45), nullable=True)

    def __init__(self, msg_date, msg_from, msg_to, msg_subject, msg_body, msg_status):
        self.msg_date = msg_date
        self.msg_from = msg_from
        self.msg_to = msg_to
        self.msg_subject = msg_subject
        self.msg_body = msg_body
        self.msg_status = msg_status

    def __repr__(self):
        return f'<TocMessages {self.msg_id}>'

class TocNotification(db.Model):
    __tablename__ = 'toc_notifications'

    not_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    not_date = db.Column(db.DateTime)
    not_address = db.Column(db.String(45), nullable=True)
    not_subject = db.Column(db.String(100), nullable=True)
    not_body = db.Column(db.String(300), nullable=True)
    not_status = db.Column(db.String(45), nullable=True)


class TocStockOrder(db.Model):
    __tablename__ = 'toc_stock_order'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45))
    user = db.Column(db.String(45))
    item_name = db.Column(db.String(100))
    order_qty = db.Column(db.Float)
    comments = db.Column(db.String(100))
    order_status = db.Column(db.String(45))
    order_status_date = db.Column(db.DateTime)

class TocReplenishOrder(db.Model):
    __tablename__ = 'toc_replenish_order'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    item_name = db.Column(db.String(100), nullable=True)
    replenish_qty = db.Column(db.Float, nullable=True)
    comments = db.Column(db.String(100), nullable=True)
    received_qty = db.Column(db.Float, nullable=True)
    rejected_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, nullable=True)
    received_date = db.Column(db.DateTime, nullable=True)
    received_by = db.Column(db.String(45), nullable=True)
    received_comment = db.Column(db.String(100), nullable=True)
    pastel_ind = db.Column(db.Integer, default=0)
    save_count = db.Column(db.Float, default=0)
    pastel_date = db.Column(db.DateTime, nullable=True)

class TocProduct(db.Model):
    __tablename__ = 'toc_product'

    item_sku = db.Column(db.String(45), primary_key=True, nullable=False)
    item_name = db.Column(db.String(200), nullable=True)
    stat_group = db.Column(db.String(45), nullable=True)
    acct_group = db.Column(db.String(45), nullable=True)
    retail_price = db.Column(db.Float, nullable=True)
    cost_price = db.Column(db.Float, nullable=True)
    wh_price = db.Column(db.Float, nullable=True)
    cann_cost_price = db.Column(db.Float, nullable=True)
    product_url = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(200), nullable=True)
    stock_ord_ind = db.Column(db.Integer, nullable=True)
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    update_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class TOCReplenishCtrl(db.Model):
    __tablename__ = 'toc_replenish_ctrl'

    order_id = db.Column(db.String(45), primary_key=True)
    shop_id = db.Column(db.String(45), nullable=True)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    order_status = db.Column(db.String(45), nullable=True)
    order_status_date = db.Column(db.DateTime, nullable=True)
    tracking_code = db.Column(db.String(45), nullable=True)
    sold_qty = db.Column(db.Integer, nullable=True)
    replenish_qty = db.Column(db.Integer, nullable=True)
    sent_from = db.Column(db.String(45), nullable=True)

class TocStock(db.Model):
    __tablename__ = 'toc_stock'

    shop_id = db.Column(db.String(20), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    stock_qty_date = db.Column(db.DateTime,  nullable=False)
    product_name = db.Column(db.String(100), nullable=True)
    stock_count = db.Column(db.Float, nullable=True)
    count_by = db.Column(db.String(45), nullable=True)
    last_stock_qty = db.Column(db.Float, nullable=True)
    calc_stock_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, nullable=False, default=0)
    variance_rsn = db.Column(db.String(45), nullable=True)
    stock_transfer = db.Column(db.Float, nullable=True, default=0)
    shop_name = db.Column(db.String(45), nullable=True)
    rejects_qty = db.Column(db.Float, nullable=True)
    rcv_damaged = db.Column(db.Float, nullable=True)
    final_stock_qty = db.Column(db.Float, nullable=True)
    replenish_id = db.Column(db.String(45), nullable=True)
    comments = db.Column(db.String(150), nullable=True)
    pastel_ind = db.Column(db.Integer, default=0, nullable=True)
    pastel_count = db.Column(db.Float, nullable=True)
    pastel_date =  db.Column(db.DateTime, nullable=True)

class TOCStockVariance(db.Model):
    __tablename__ = 'toc_stock_variance'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Use datetime.utcnow for default
    shop_id = db.Column(db.String(20), nullable=True)
    sku = db.Column(db.String(45), nullable=True)
    stock_qty_date = db.Column(db.DateTime, nullable=True)
    product_name = db.Column(db.String(100), nullable=True)
    stock_count = db.Column(db.Float, nullable=True)
    count_by = db.Column(db.String(45), nullable=True)
    last_stock_qty = db.Column(db.Float, nullable=True)
    calc_stock_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, default=0)  # Ensure default is numeric
    # variance_rsn = db.Column(db.String(45), nullable=True)
    stock_recount = db.Column(db.Float, nullable=True)
    shop_name = db.Column(db.String(45), nullable=True)
    rejects_qty = db.Column(db.Float, nullable=True)
    final_stock_qty = db.Column(db.Float, nullable=True)
    replenish_id = db.Column(db.String(45), nullable=True)
    comments = db.Column(db.String(150), nullable=True)


class TocRole(db.Model):
    __tablename__ = 'toc_roles'

    role = db.Column(db.String(20), primary_key=True, nullable=False)
    exclusions = db.Column(db.String(200), default=None)


class TOCUserActivity(db.Model):
    __tablename__ = 'toc_user_activity'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    actv_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    user = db.Column(db.String(45), nullable=True)
    shop = db.Column(db.String(45), nullable=True)
    activity = db.Column(db.String(100), nullable=True)


class TocSalesLog(db.Model):
    __tablename__ = 'toc_sales_log'

    run_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    search_from = db.Column(db.String(40), nullable=True)
    num_of_sales = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(2), nullable=True)
    comment = db.Column(db.String(200), nullable=True)

class TOCWeeks(db.Model):
    __tablename__ = 'toc_weeks'

    week = db.Column(db.String(10), primary_key=True)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)

class TOCCasuals(db.Model):
    __tablename__ = 'toc_casuals'

    shop_id = db.Column(db.String(45), primary_key=True)
    week = db.Column(db.String(45), primary_key=True)
    date = db.Column(db.Date, primary_key=True)
    casuals = db.Column(db.String(200), nullable=True)
    confirmed_by = db.Column(db.String(45), nullable=True)
    confirmation_date = db.Column(db.DateTime, nullable=True)

class TOCCasualsCtrl(db.Model):
    __tablename__ = 'toc_casuals_ctrl'

    shop_id = db.Column(db.String(45), primary_key=True)
    week = db.Column(db.String(45), primary_key=True)
    status = db.Column(db.String(45), nullable=True)
    status_date = db.Column(db.DateTime,  nullable=True)
    confirmed_by = db.Column(db.String(45), nullable=True)

class TOCOpenAI(db.Model):
    __tablename__ = 'toc_openai'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    shop_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_query = db.Column(db.Text, nullable=False)

class TocCountCtrl(db.Model):
    __tablename__ = 'toc_count_ctrl'

    count_id = db.Column(db.String(45), primary_key=True)
    name = db.Column(db.String(45))
    username = db.Column(db.String(45))
    shop_id = db.Column(db.String(45))
    shop_name = db.Column(db.String(45))
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class TocDamaged(db.Model):
    __tablename__ = 'toc_damaged'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    item_name = db.Column(db.String(100), nullable=True)
    rejected_qty = db.Column(db.Float, nullable=True)  # Sent Damaged
    rcv_damaged = db.Column(db.Float, nullable=True)   # Received Damaged
    variance = db.Column(db.Float, nullable=True)      # Difference between sent and received damaged

class TocShipday(db.Model):
    __tablename__ = 'toc_shipday'

    wc_orderid = db.Column(db.Integer, primary_key=True, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    wc_name = db.Column(db.String(45), nullable=True)
    wc_email = db.Column(db.String(45), nullable=True)
    wc_phone = db.Column(db.String(45), nullable=True)
    shop_name = db.Column(db.String(45), nullable=True)
    status = db.Column(db.String(45), nullable=True)
    update_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ls_order_id = db.Column(db.String(45), nullable=True)
    shipday_id = db.Column(db.String(45), nullable=True)
    total_amt = db.Column(db.Float, nullable=True)
    closest_shop_json = db.Column(db.JSON)


    ###################  GIL INSURANCE  ######################

class GilInsured(db.Model):
    __tablename__ = 'gil_insured'

    id = db.Column(db.Integer, primary_key=True)
    ref_number = db.Column(db.String(45))
    received_date = db.Column(db.Date)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    birth_date = db.Column(db.Date)
    father_name = db.Column(db.String(255))
    id_number = db.Column(db.String(10))
    claim_number = db.Column(db.String(20))
    claim_type = db.Column(db.String(20), nullable=False, default='סיעוד')
    gender = db.Column(db.String(20))
    status = db.Column(db.String(10), default='פתוחה')
    city = db.Column(db.String(100))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    koopa = db.Column(db.String(50))  # Health fund
    clinic = db.Column(db.String(100))
    recurring_appointments = db.Column(db.String(100))
    insurance = db.Column(db.String(20))
    notes = db.Column(db.Text)
    photo = db.Column(db.String(255))  # store the filename only
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    investigator = db.Column(db.String(200))

class GilInvestigator(db.Model):
    __tablename__ = 'gil_investigator'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)  # Record creation timestamp

    full_name = db.Column(db.String(100), nullable=False)
    emp_id = db.Column(db.String(50), unique=True)  # Internal employee reference

    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(150))

    start_work = db.Column(db.Date)
    active_status = db.Column(db.Enum('Active', 'Inactive', 'Suspended'), default='Active')

    last_payment = db.Column(db.Numeric(12, 2), default=0.00)
    last_payment_date = db.Column(db.Date)

    payment_frequency = db.Column(db.Enum('Monthly', 'Weekly', 'Per Case'), default='Per Case')
    total_cases = db.Column(db.Integer, default=0)
    rating = db.Column(db.Numeric(3, 2))  # Performance rating (0.00 - 5.00)

    notes = db.Column(db.Text)


class GilContact(db.Model):
    __tablename__ = 'gil_contacts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    insured_id = db.Column(db.Integer, db.ForeignKey('gil_insured.id', ondelete='CASCADE'), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)

    full_name = db.Column(db.String(150), nullable=False)
    relation = db.Column(db.String(100))
    address = db.Column(db.Text)
    phone_1 = db.Column(db.String(50))
    phone_2 = db.Column(db.String(50))
    social_media_1 = db.Column(db.String(255))
    social_media_2 = db.Column(db.String(255))
    notes = db.Column(db.Text)

    # Relationship to gil_insured
    insured = db.relationship('GilInsured', backref=db.backref('contacts', cascade='all, delete-orphan'))



