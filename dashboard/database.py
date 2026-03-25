from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    job_url = Column(Text)
    workday_url = Column(Text)
    status = Column(String(50), default="To Apply")
    date_added = Column(DateTime, default=datetime.utcnow)
    date_applied = Column(DateTime, nullable=True)
    last_status_check = Column(DateTime, nullable=True)
    job_description = Column(Text)
    tailored_resume = Column(Text)
    notes = Column(Text)
    salary_range = Column(String(100))
    location = Column(String(200))
    source = Column(String(100), default="Manual")


class CoffeeChat(Base):
    __tablename__ = "coffee_chats"
    id = Column(Integer, primary_key=True, index=True)
    person_name = Column(String(200), nullable=False)
    company = Column(String(200))
    role = Column(String(200))
    linkedin_url = Column(Text)
    email = Column(String(200))
    status = Column(String(50), default="To Reach Out")
    date_added = Column(DateTime, default=datetime.utcnow)
    date_reached_out = Column(DateTime, nullable=True)
    date_meeting = Column(DateTime, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    notes = Column(Text)
    next_action = Column(Text)
    meeting_notes = Column(Text)


class EmailOutreach(Base):
    __tablename__ = "email_outreach"
    id = Column(Integer, primary_key=True, index=True)
    recipient_name = Column(String(200), nullable=False)
    recipient_email = Column(String(200), nullable=False)
    company = Column(String(200))
    subject = Column(String(500))
    status = Column(String(50), default="Draft")
    date_sent = Column(DateTime, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    notes = Column(Text)
    email_body = Column(Text)


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)
    is_base = Column(Boolean, default=False)


# ── NEW MODELS ────────────────────────────────────────────────────────────────

class Notification(Base):
    """System notifications: login failures, status updates, follow-up reminders."""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), default="info")   # info | warning | error | success
    title = Column(String(300), nullable=False)
    message = Column(Text)
    job_id = Column(Integer, nullable=True)      # linked job (optional)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApplicationAnswer(Base):
    """Saved answers to common job application questions, reused across all jobs."""
    __tablename__ = "application_answers"
    id = Column(Integer, primary_key=True, index=True)
    question_key = Column(String(100), nullable=False, unique=True)   # machine key
    question_label = Column(String(300), nullable=False)              # human label
    answer = Column(Text, default="")
    category = Column(String(100), default="General")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkdayCredential(Base):
    """Per-company Workday login credentials stored encrypted."""
    __tablename__ = "workday_credentials"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False)
    workday_domain = Column(String(300))   # e.g. apple.wd5.myworkdayjobs.com
    email = Column(String(200))
    password_enc = Column(Text)            # Fernet-encrypted
    notes = Column(Text)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Default questions seeded on first run ─────────────────────────────────────

DEFAULT_QUESTIONS = [
    # Personal
    ("first_name",           "First Name",                           "Personal"),
    ("last_name",            "Last Name",                            "Personal"),
    ("email",                "Email Address",                        "Personal"),
    ("phone",                "Phone Number",                         "Personal"),
    ("address_line1",        "Street Address",                       "Personal"),
    ("city",                 "City",                                 "Personal"),
    ("state",                "State / Province",                     "Personal"),
    ("zip_code",             "ZIP / Postal Code",                    "Personal"),
    ("country",              "Country",                              "Personal"),
    ("linkedin_url",         "LinkedIn Profile URL",                 "Personal"),
    ("github_url",           "GitHub / Portfolio URL",               "Personal"),
    # Work Authorization
    ("work_authorized_us",   "Are you legally authorized to work in the US?",   "Work Authorization"),
    ("sponsorship_required", "Will you now or in the future require sponsorship?", "Work Authorization"),
    # Preferences
    ("willing_to_relocate",  "Are you willing to relocate?",         "Preferences"),
    ("work_arrangement",     "Preferred work arrangement (Remote / Hybrid / On-site)", "Preferences"),
    ("desired_salary",       "Desired salary / compensation range",  "Preferences"),
    ("available_start_date", "Earliest available start date",        "Preferences"),
    # Education
    ("education_level",      "Highest level of education",           "Education"),
    ("university",           "University / School name",             "Education"),
    ("major",                "Field of study / Major",               "Education"),
    ("graduation_year",      "Graduation year",                      "Education"),
    ("gpa",                  "GPA (leave blank to omit)",            "Education"),
    # Experience
    ("years_experience",     "Total years of relevant experience",   "Experience"),
    # EEO (optional)
    ("veteran_status",       "Veteran status",                       "EEO (Optional)"),
    ("disability_status",    "Disability status",                    "EEO (Optional)"),
    ("gender",               "Gender (optional)",                    "EEO (Optional)"),
    ("ethnicity",            "Ethnicity (optional)",                 "EEO (Optional)"),
    ("how_heard",            "How did you hear about this role?",    "EEO (Optional)"),
]


def seed_questions(db):
    for key, label, category in DEFAULT_QUESTIONS:
        exists = db.query(ApplicationAnswer).filter(ApplicationAnswer.question_key == key).first()
        if not exists:
            db.add(ApplicationAnswer(question_key=key, question_label=label, category=category))
    db.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_questions(db)
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
