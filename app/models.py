from email.policy import default

from . import db
from flask_sqlalchemy import SQLAlchemy
import datetime
from datetime import datetime,timezone,date
from sqlalchemy.dialects.mysql import MEDIUMTEXT, LONGTEXT
from sqlalchemy import Enum  # add this import if not already in your models file


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


class TOCOpenAI(db.Model):
    __tablename__ = 'toc_openai'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    shop_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_query = db.Column(db.Text, nullable=False)




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
    status = db.Column(db.String(50), default='נתקבל')
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
    parkinson_ind = db.Column( db.SmallInteger,   nullable=False,  server_default="0" )

    pw_process_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_pw_process.process_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    pw_version_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_pw_process_version.version_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    pw_process = db.relationship("GilPwProcess", foreign_keys=[pw_process_id], lazy="joined")
    pw_version = db.relationship("GilPwProcessVersion", foreign_keys=[pw_version_id], lazy="joined")


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
    active_status = db.Column(
        db.Enum('Active', 'Inactive', 'Suspended'),
        default='Active'
    )

    last_payment = db.Column(db.Numeric(12, 2), default=0.00)
    last_payment_date = db.Column(db.Date)

    payment_frequency = db.Column(
        db.Enum('Monthly', 'Weekly', 'Per Case'),
        default='Per Case'
    )
    total_cases = db.Column(db.Integer, default=0)
    rating = db.Column(db.Numeric(3, 2))  # Performance rating (0.00 - 5.00)

    notes = db.Column(db.Text)

    # 🔗 Link to toc_users
    user_id = db.Column(db.Integer, db.ForeignKey('toc_users.id'), nullable=True, unique=True)
    user = db.relationship("User", backref="investigator_profile", uselist=False)



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


class GilKoopa(db.Model):
    __tablename__ = 'gil_koopa'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    koopa_name = db.Column(db.String(45), nullable=True)

    def __init__(self, koopa_name=None):
        self.koopa_name = koopa_name

    def __repr__(self):
        return f'<GilKoopa {self.koopa_name}>'


class GilClinics(db.Model):
    __tablename__ = 'gil_clinics'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    clinic_name = db.Column(db.String(45), nullable=True)

    def __init__(self, clinic_name=None):
        self.clinic_name = clinic_name

    def __repr__(self):
        return f'<GilClinics {self.clinic_name}>'




class GilAppointment(db.Model):
    __tablename__ = 'gil_appointments'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('gil_insured.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator_id = db.Column(db.Integer, db.ForeignKey('toc_users.id'))
    initiator_id = db.Column(db.Integer, db.ForeignKey('toc_users.id'))

    appointment_date = db.Column(db.Date, nullable=False)
    time_from = db.Column(db.DateTime, nullable=False)
    time_to = db.Column(db.DateTime, nullable=False)

    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="נוצר")

    place = db.Column(db.String(255))
    doctor = db.Column(db.String(255))
    koopa = db.Column(db.String(100))

    # ✅ Corrected relationship
    investigators = db.relationship("GilInvestigatorAppointment", back_populates="appointment")

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "time_from": str(self.time_from) if self.time_from else None,
            "time_to": str(self.time_to) if self.time_to else None,
            "status": self.status,
            "address": self.address,
            "notes": self.notes,
            "place": self.place,
            "doctor": self.doctor,
            "koopa": self.koopa,
        }


class GilInvestigatorAppointment(db.Model):
    __tablename__ = 'gil_investigator_appointments'

    appointment_id = db.Column(db.Integer, db.ForeignKey('gil_appointments.id', ondelete="CASCADE"), primary_key=True)
    investigator_id = db.Column(db.Integer, db.ForeignKey('gil_investigator.id', ondelete="CASCADE"), primary_key=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('toc_users.id'))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Match back_populates
    appointment = db.relationship("GilAppointment", back_populates="investigators")
    investigator = db.relationship("GilInvestigator")
    assigned_user = db.relationship("User", foreign_keys=[assigned_by])



class GilInvestigatorCase(db.Model):
    __tablename__ = 'gil_investigator_case'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    insured_id = db.Column(db.Integer, db.ForeignKey('gil_insured.id'), nullable=False, index=True)
    investigator_id = db.Column(db.Integer, db.ForeignKey('gil_investigator.id'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('toc_users.id'), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    insured = db.relationship('GilInsured', backref=db.backref('investigator_links', cascade='all, delete-orphan'))
    investigator = db.relationship('GilInvestigator', backref=db.backref('case_links', cascade='all, delete-orphan'))
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])



class GilTask(db.Model):
    __tablename__ = "gil_tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    case_id = db.Column(db.Integer, db.ForeignKey("gil_insured.id", ondelete="CASCADE"), nullable=False, index=True)

    # ✅ NEW: generic assignee (replaces investigator_id)
    user_id = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="RESTRICT"), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(50), default="פתוחה", index=True)

    creator_id = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # PW integration (optional now, very useful soon)
    source = db.Column(db.String(30), default="manual")  # manual | process_wizard
    # PW fields (keep as plain columns until PW tables/models are implemented)
    milestone_instance_id = db.Column(db.Integer, nullable=True)
    blocking_key = db.Column(db.String(80), nullable=True)

    # Relationships (nice to have)
    assignee = db.relationship("User", foreign_keys=[user_id])
    creator = db.relationship("User", foreign_keys=[creator_id])


class GilReport(db.Model):
    __tablename__ = 'gil_reports'
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, nullable=False)
    insurer_id = db.Column(db.Integer)
    report_type = db.Column(db.String(50), nullable=False)
    template_key = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(255))
    status = db.Column(db.String(20), default='Draft')      # Empty | Draft | Final | Submitted | Revised
    version_no = db.Column(db.Integer, default=0)           # 0 for first Final; increments on revisions
    reference_no = db.Column(db.String(50))                 # e.g. 65951 or 65951.1

    editor_json = db.Column(db.Text)        # or MEDIUMTEXT
    generated_html = db.Column(db.Text)     # or LONGTEXT
    generated_pdf_path = db.Column(db.String(255))

    created_by = db.Column(db.Integer)
    updated_by = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    finalize_mode = db.Column(db.String(20))


class GilReportPhoto(db.Model):
    __tablename__ = 'gil_report_photos'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer,  nullable=False)

    # Dropbox path of the original and chosen rendition
    dropbox_path = db.Column(db.String(512), nullable=False)        # e.g., /Phoenix/InsuredName/photos/IMG_1234.jpg
    caption = db.Column(db.String(255))
    order_index = db.Column(db.Integer, default=0)
    placement = db.Column(db.String(20))  # 'full', 'half-left', 'half-right', 'stack-top', 'stack-bottom'

    # cached meta (for fast layout)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    orientation = db.Column(db.String(10))  # 'landscape' | 'portrait' | 'square'


class GilTrackingReport(db.Model):
    __tablename__ = 'gil_tracking_reports'

    report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    ref_number = db.Column(db.String(50), nullable=False)

    insured_id = db.Column(
        db.Integer,
        db.ForeignKey('gil_insured.id', ondelete='CASCADE'),
        nullable=False
    )

    investigator_id = db.Column(
        db.Integer,
        db.ForeignKey('gil_investigator.id', ondelete='RESTRICT'),
        nullable=False
    )

    report_date = db.Column(db.Date, nullable=False)
    mileage_km = db.Column(db.Integer, nullable=True)

    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Draft')

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('ref_number', 'report_date', name='uq_tracking_ref_day'),
        db.Index('idx_tracking_insured', 'insured_id'),
        db.Index('idx_tracking_investigator', 'investigator_id'),
        db.Index('idx_tracking_date', 'report_date'),
    )

    insured = db.relationship('GilInsured', backref=db.backref('tracking_reports', lazy='select'))
    investigator = db.relationship('GilInvestigator', backref=db.backref('tracking_reports', lazy='select'))

    activities = db.relationship(
        'GilTrackingReportActivity',
        backref='report',
        cascade='all, delete-orphan',
        order_by='GilTrackingReportActivity.sort_order.asc()'
    )

    # ✅ IMPORTANT: DO NOT use backref='report' here, because GilTrackingExpense already has .report
    expenses = db.relationship(
        'GilTrackingExpense',
        back_populates='report',
        cascade='all, delete-orphan',
        lazy='select',
        order_by='GilTrackingExpense.expense_id.asc()'
    )

    @property
    def active_expenses(self):
        return [e for e in (self.expenses or []) if not getattr(e, "deleted_ind", False)]


class GilTrackingReportActivity(db.Model):
    __tablename__ = 'gil_tracking_report_activities'

    activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    report_id = db.Column(
        db.Integer,
        db.ForeignKey('gil_tracking_reports.report_id', ondelete='CASCADE'),
        nullable=False
    )

    # -------------------------
    # NEW: versioning + source
    # -------------------------
    set_no = db.Column(db.Integer, nullable=False, default=1)
    is_current = db.Column(db.Boolean, nullable=False, default=True)
    source = db.Column(
        Enum('investigator', 'admin', name='gil_tracking_activity_source'),
        nullable=False,
        default='investigator'
    )
    created_by_user_id = db.Column(db.Integer, nullable=True)

    # -------------------------
    # Existing fields
    # -------------------------
    activity_time = db.Column(db.Time, nullable=False)
    description = db.Column(db.Text, nullable=False)

    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_activity_report', 'report_id'),
        db.Index('idx_activity_report_current', 'report_id', 'is_current'),
        db.Index('idx_activity_report_set', 'report_id', 'set_no'),
    )

    ###################### Expenses ####################



class GilTrackingExpense(db.Model):
    __tablename__ = "gil_tracking_expenses"

    expense_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    report_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_tracking_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    investigator_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_investigator.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("toc_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    expense_date = db.Column(db.Date, nullable=True, default=date.today)
    description = db.Column(db.String(255), nullable=False, default="")
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    currency = db.Column(db.String(3), nullable=False, default="ILS")
    category = db.Column(db.String(50), nullable=True)

    deleted_ind = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ match GilTrackingReport.expenses(back_populates='report')
    report = db.relationship("GilTrackingReport", back_populates="expenses")

    media = db.relationship(
        "GilTrackingExpenseMedia",
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy="select"
    )


class GilTrackingExpenseMedia(db.Model):
    __tablename__ = "gil_tracking_expense_media"

    media_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    expense_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_tracking_expenses.expense_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    storage_provider = db.Column(db.String(20), nullable=False, default="dropbox")

    file_name = db.Column(db.String(255), nullable=False, default="")
    file_ext = db.Column(db.String(10), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    # Dropbox metadata (source of truth is path)
    dropbox_path = db.Column(db.Text, nullable=False)
    dropbox_file_id = db.Column(db.String(120), nullable=True)
    shared_url = db.Column(db.Text, nullable=True)
    thumb_url = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    expense = db.relationship("GilTrackingExpense", back_populates="media")


####################  Media tracking  ######################
class GilMedia(db.Model):
    __tablename__ = "gil_media"

    media_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    insured_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_insured.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    media_type = db.Column(db.String(20), nullable=False, default="photos")

    dropbox_path = db.Column(db.String(1024), nullable=False)
    file_name    = db.Column(db.String(255), nullable=True)

    taken_at   = db.Column(db.DateTime, nullable=True)
    taken_date = db.Column(db.Date, nullable=True)

    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by_user_id = db.Column(db.Integer, nullable=True)

    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index("idx_media_insured_date", "insured_id", "taken_date"),
        db.Index("idx_media_type", "media_type"),
    )



class GilTrackingReportMedia(db.Model):
    __tablename__ = "gil_tracking_report_media"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    tracking_report_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_tracking_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    media_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_media.media_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    tag = db.Column(db.String(50), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_by_user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("tracking_report_id", "media_id", name="uq_tracking_report_media"),
    )


################  Case notes  ###################


class GilCaseNote(db.Model):
    __tablename__ = "gil_case_notes"

    note_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    insured_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_insured.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("toc_users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    note_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    note_text = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    insured = db.relationship("GilInsured", backref=db.backref("case_notes", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])

    photos = db.relationship(
        "GilCaseNotePhoto",
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
        order_by="GilCaseNotePhoto.uploaded_at.asc()",
    )

    def __repr__(self):
        return f"<GilCaseNote note_id={self.note_id} insured_id={self.insured_id}>"


class GilCaseNotePhoto(db.Model):
    __tablename__ = "gil_case_note_photos"

    photo_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    note_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_case_notes.note_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    dropbox_path = db.Column(db.String(1024), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)

    uploaded_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("toc_users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    note = db.relationship("GilCaseNote", back_populates="photos")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_user_id])  # adjust if needed

    def __repr__(self):
        return f"<GilCaseNotePhoto photo_id={self.photo_id} note_id={self.note_id}>"

########################### Process Wizard #################################

from sqlalchemy import UniqueConstraint

class GilPwProcess(db.Model):
    __tablename__ = "gil_pw_process"

    process_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    insurance_company = db.Column(db.String(80), nullable=False)
    claim_type = db.Column(db.String(80), nullable=False)
    process_name = db.Column(db.String(120), nullable=False)
    active_ind = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    # ✅ NEW: points to the currently "published" version for this process
    published_version_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_pw_process_version.version_id", ondelete="SET NULL"),
        nullable=True
    )

    # ✅ relationship to the published version (uses published_version_id)
    published_version = db.relationship(
        "GilPwProcessVersion",
        foreign_keys=[published_version_id],
        post_update=True,
        lazy="joined"
    )

    __table_args__ = (
        db.UniqueConstraint("insurance_company", "claim_type", name="uq_pw_process"),
    )

    # ✅ FIX: process -> versions must use ONLY GilPwProcessVersion.process_id
    versions = db.relationship(
        "GilPwProcessVersion",
        back_populates="process",
        foreign_keys="GilPwProcessVersion.process_id",
        cascade="all, delete-orphan",
        lazy="select"
    )

class GilPwStatusStep(db.Model):
    __tablename__ = "gil_pw_status_step"

    step_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    version_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_pw_process_version.version_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    step_order = db.Column(db.Integer, nullable=False)

    status_code = db.Column(
        db.String(50),
        db.ForeignKey("dor_case_status.status_code"),
        nullable=False
    )

    is_terminal = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("version_id", "status_code", name="uq_pw_step"),
        db.UniqueConstraint("version_id", "step_order", name="uq_pw_step_order"),
    )

    # relationships
    status = db.relationship("DorCaseStatus")
    version = db.relationship("GilPwProcessVersion", back_populates="steps")

    activities = db.relationship(
        "GilPwStepActivity",
        back_populates="step",
        cascade="all, delete-orphan"
    )

class GilPwStepActivity(db.Model):
    __tablename__ = "gil_pw_step_activity"

    activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    step_id = db.Column(db.Integer, db.ForeignKey("gil_pw_status_step.step_id", ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    activity_type = db.Column(db.String(30), default="task", nullable=False)   # task|check|doc|external
    blocking_ind = db.Column(db.Boolean, default=True, nullable=False)
    blocked_status_code = db.Column(db.String(50), nullable=True)

    default_assignee_role = db.Column(db.String(50), nullable=True)

    # ✅ NEW
    assignee_user_id = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True, index=True)

    due_days_offset = db.Column(db.Integer, nullable=True)

    active_ind = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=10, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    step = db.relationship("GilPwStatusStep", back_populates="activities")

    # optional (nice for joins later)
    assignee_user = db.relationship("User", foreign_keys=[assignee_user_id])

class GilPwCaseActivity(db.Model):
    __tablename__ = "gil_pw_case_activity"

    case_activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    case_id = db.Column(db.Integer, db.ForeignKey("gil_insured.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("gil_pw_step_activity.activity_id", ondelete="CASCADE"), nullable=False)

    status = db.Column(db.String(30), default="open", nullable=False, index=True)  # open|done|skipped
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)
    note = db.Column(db.Text, nullable=True)

    task_id = db.Column(db.Integer, db.ForeignKey("gil_tasks.id", ondelete="SET NULL"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "activity_id", name="uq_case_activity"),
    )

    activity = db.relationship("GilPwStepActivity")

class GilCaseStatusHistory(db.Model):
    __tablename__ = "gil_case_status_history"

    history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    case_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_insured.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    status_code = db.Column(db.String(50), nullable=False, index=True)
    process_id = db.Column(db.Integer, nullable=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    ended_at = db.Column(db.DateTime, nullable=True)
    ended_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    duration_minutes = db.Column(db.Integer, nullable=True)

    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class GilPwCaseStatusAudit(db.Model):
    __tablename__ = "gil_pw_case_status_audit"

    audit_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    case_id = db.Column(db.Integer, db.ForeignKey("gil_insured.id", ondelete="CASCADE"), nullable=False, index=True)
    process_id = db.Column(db.Integer, db.ForeignKey("gil_pw_process.process_id", ondelete="RESTRICT"), nullable=True, index=True)
    version_id = db.Column(db.Integer, db.ForeignKey("gil_pw_process_version.version_id", ondelete="RESTRICT"), nullable=True, index=True)

    status_code = db.Column(db.String(50), nullable=False, index=True)
    status_name = db.Column(db.String(100), nullable=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_by_user_id = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    ended_at = db.Column(db.DateTime, nullable=True)
    ended_by_user_id = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    duration_seconds = db.Column(db.Integer, nullable=True)
    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    started_by = db.relationship("User", foreign_keys=[started_by_user_id])
    ended_by = db.relationship("User", foreign_keys=[ended_by_user_id])

class GilPwProcessVersion(db.Model):
    __tablename__ = "gil_pw_process_version"

    version_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    process_id = db.Column(
        db.Integer,
        db.ForeignKey("gil_pw_process.process_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    version_no = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)  # draft|published|archived

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    published_at = db.Column(db.DateTime, nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("toc_users.id", ondelete="SET NULL"), nullable=True)

    note = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("process_id", "version_no", name="uq_process_version"),
        db.Index("ix_version_process", "process_id"),
        db.Index("ix_version_status", "status"),
    )

    # ✅ FIX: version -> process must use ONLY process_id
    process = db.relationship(
        "GilPwProcess",
        back_populates="versions",
        foreign_keys=[process_id]
    )

    # ✅ steps belong to version
    steps = db.relationship(
        "GilPwStatusStep",
        back_populates="version",
        cascade="all, delete-orphan"
    )

class DorCaseStatus(db.Model):
    __tablename__ = "dor_case_status"

    status_code = db.Column(db.String(50), primary_key=True)
    status_description = db.Column(db.String(100), nullable=False, unique=True)
    active_ind = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<DorCaseStatus {self.status_code}>"


