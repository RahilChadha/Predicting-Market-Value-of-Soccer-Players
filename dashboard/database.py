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
    status = Column(String(50), default="To Apply")  # To Apply, Applied, Phone Screen, Interview, Offer, Rejected, Withdrawn
    date_added = Column(DateTime, default=datetime.utcnow)
    date_applied = Column(DateTime, nullable=True)
    last_status_check = Column(DateTime, nullable=True)
    job_description = Column(Text)
    tailored_resume = Column(Text)
    notes = Column(Text)
    salary_range = Column(String(100))
    location = Column(String(200))
    source = Column(String(100), default="Manual")  # LinkedIn, Manual, Referral, etc.


class CoffeeChat(Base):
    __tablename__ = "coffee_chats"
    id = Column(Integer, primary_key=True, index=True)
    person_name = Column(String(200), nullable=False)
    company = Column(String(200))
    role = Column(String(200))
    linkedin_url = Column(Text)
    email = Column(String(200))
    status = Column(String(50), default="To Reach Out")  # To Reach Out, Message Sent, Scheduled, Completed, Follow Up, No Response
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
    status = Column(String(50), default="Draft")  # Draft, Sent, Replied, Follow Up, No Response
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


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
