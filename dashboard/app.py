"""
Job Tracking Dashboard - FastAPI Backend
"""

import os
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from database import (
    init_db, get_db,
    Job, CoffeeChat, EmailOutreach, Resume,
    Notification, ApplicationAnswer, WorkdayCredential
)
from automation.workday import get_workday_status, apply_to_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Encryption helpers (Fernet, key from .env or auto-generated) ──────────────

def _get_fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        # Generate and print once so user can save it
        key = Fernet.generate_key().decode()
        logger.warning(
            f"\n⚠  No ENCRYPTION_KEY in .env — generated a temporary one.\n"
            f"   Add this to your .env to persist encrypted passwords:\n"
            f"   ENCRYPTION_KEY={key}\n"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_password(plain: str) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_password(enc: str) -> str:
    if not enc:
        return ""
    try:
        return _get_fernet().decrypt(enc.encode()).decode()
    except Exception:
        return ""


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title="Job Tracking Dashboard", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    company: str
    title: str
    job_url: Optional[str] = None
    workday_url: Optional[str] = None
    status: Optional[str] = "To Apply"
    job_description: Optional[str] = None
    notes: Optional[str] = None
    salary_range: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = "Manual"

class JobUpdate(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    job_url: Optional[str] = None
    workday_url: Optional[str] = None
    status: Optional[str] = None
    job_description: Optional[str] = None
    tailored_resume: Optional[str] = None
    notes: Optional[str] = None
    salary_range: Optional[str] = None
    location: Optional[str] = None
    date_applied: Optional[datetime] = None

class CoffeeChatCreate(BaseModel):
    person_name: str
    company: Optional[str] = None
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "To Reach Out"
    date_meeting: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None

class CoffeeChatUpdate(BaseModel):
    person_name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    date_meeting: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    meeting_notes: Optional[str] = None
    date_reached_out: Optional[datetime] = None

class EmailCreate(BaseModel):
    recipient_name: str
    recipient_email: str
    company: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = "Draft"
    email_body: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None

class EmailUpdate(BaseModel):
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    company: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    email_body: Optional[str] = None
    date_sent: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None

class ResumeCreate(BaseModel):
    name: str
    content: str
    is_base: Optional[bool] = False

class TailorRequest(BaseModel):
    job_description: str
    job_id: Optional[int] = None

class AnswerUpsert(BaseModel):
    question_key: str
    answer: str

class CredentialCreate(BaseModel):
    company_name: str
    workday_domain: Optional[str] = None
    email: Optional[str] = None
    password: str                          # plain text in → encrypted at rest
    notes: Optional[str] = None

class CredentialUpdate(BaseModel):
    company_name: Optional[str] = None
    workday_domain: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None

class ApplyRequest(BaseModel):
    job_id: int
    password: Optional[str] = None         # password entered in dashboard UI
    email: Optional[str] = None


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


# ══════════════════════════════════════════════════════════════════════════════
# JOBS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [_job_dict(j) for j in db.query(Job).order_by(Job.date_added.desc()).all()]

@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = Job(**payload.dict())
    db.add(job); db.commit(); db.refresh(job)
    return _job_dict(job)

@app.put("/api/jobs/{job_id}")
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    job = _get_or_404(db, Job, job_id)
    for k, v in payload.dict(exclude_none=True).items():
        setattr(job, k, v)
    db.commit(); db.refresh(job)
    return _job_dict(job)

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = _get_or_404(db, Job, job_id)
    db.delete(job); db.commit()
    return {"message": "Deleted"}


@app.post("/api/jobs/{job_id}/check-status")
async def check_job_status(job_id: int, db: Session = Depends(get_db)):
    job = _get_or_404(db, Job, job_id)
    if not job.workday_url:
        raise HTTPException(400, "No Workday URL set for this job")

    cred = _find_credential(db, job.workday_url)
    email, password = _resolve_cred(cred)
    if not email or not password:
        raise HTTPException(400, "No credentials found. Add them in Job Setup > Passwords.")

    result = await get_workday_status(job.workday_url, email, password)
    if result.get("success"):
        job.status = result["status"]
        job.last_status_check = datetime.utcnow()
        db.commit()
    elif result.get("wrong_password"):
        _add_notification(db, "error",
            f"Wrong password for {job.company}",
            f"Login failed for {job.company}. Please update the password in Job Setup > Passwords.",
            job_id=job.id)
    return result


@app.post("/api/jobs/{job_id}/apply")
async def apply_job(job_id: int, payload: ApplyRequest, db: Session = Depends(get_db)):
    job = _get_or_404(db, Job, job_id)
    url = job.workday_url or job.job_url
    if not url:
        raise HTTPException(400, "No job URL configured")

    # Resolve credentials: UI-provided > stored credential > .env fallback
    email = payload.email or ""
    password = payload.password or ""

    if not password:
        cred = _find_credential(db, url)
        email, password = _resolve_cred(cred)
        if not email:
            email = os.getenv("WORKDAY_EMAIL", "")
        if not password:
            password = os.getenv("WORKDAY_PASSWORD", "")

    if not email or not password:
        raise HTTPException(400, "No credentials available. Enter password in the Apply dialog.")

    # Load saved application answers for auto-fill
    answers = {a.question_key: a.answer for a in db.query(ApplicationAnswer).all()}

    result = await apply_to_job(url, email, password, answers, job.tailored_resume or "")

    if result.get("wrong_password"):
        _add_notification(db, "error",
            f"Wrong password for {job.company}",
            f"The password you entered for {job.company} is incorrect. Please set a new password in Job Setup > Passwords.",
            job_id=job.id)
        return result

    if result.get("no_account"):
        _add_notification(db, "warning",
            f"New account created for {job.company}",
            f"No existing account was found. A new account was created with email {email}.",
            job_id=job.id)

    if result.get("success"):
        job.status = "Applied"
        job.date_applied = datetime.utcnow()
        # Save credential if new
        if payload.password and not _find_credential(db, url):
            cred = WorkdayCredential(
                company_name=job.company,
                workday_domain=_extract_domain(url),
                email=email,
                password_enc=encrypt_password(payload.password),
            )
            db.add(cred)
        db.commit()

    return result


@app.post("/api/jobs/check-all-statuses")
async def check_all_statuses(db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(
        Job.workday_url.isnot(None),
        Job.status.notin_(["Offer", "Rejected", "Withdrawn", "To Apply"]),
    ).all()

    results = []
    for job in jobs:
        cred = _find_credential(db, job.workday_url)
        email, password = _resolve_cred(cred)
        if not email:
            email = os.getenv("WORKDAY_EMAIL", "")
        if not password:
            password = os.getenv("WORKDAY_PASSWORD", "")
        if not email or not password:
            results.append({"job_id": job.id, "error": "No credentials", "status": "Skipped"})
            continue
        try:
            result = await get_workday_status(job.workday_url, email, password)
            if result.get("success"):
                job.status = result["status"]
                job.last_status_check = datetime.utcnow()
            elif result.get("wrong_password"):
                _add_notification(db, "error",
                    f"Wrong password for {job.company}",
                    f"Status check failed for {job.company}. Please update password in Job Setup > Passwords.",
                    job_id=job.id)
            results.append({"job_id": job.id, **result})
        except Exception as e:
            results.append({"job_id": job.id, "error": str(e)})

    db.commit()
    return {"checked": len(results), "results": results}


# ══════════════════════════════════════════════════════════════════════════════
# RESUME
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/resumes")
def list_resumes(db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name, "is_base": r.is_base, "date_created": r.date_created}
            for r in db.query(Resume).order_by(Resume.date_created.desc()).all()]

@app.post("/api/resumes", status_code=201)
def create_resume(payload: ResumeCreate, db: Session = Depends(get_db)):
    if payload.is_base:
        db.query(Resume).filter(Resume.is_base == True).update({"is_base": False})
    r = Resume(**payload.dict()); db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "name": r.name, "is_base": r.is_base}

@app.get("/api/resumes/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    r = _get_or_404(db, Resume, resume_id)
    return {"id": r.id, "name": r.name, "content": r.content, "is_base": r.is_base}

@app.post("/api/resumes/tailor")
async def tailor_resume(payload: TailorRequest, db: Session = Depends(get_db)):
    base = (db.query(Resume).filter(Resume.is_base == True).first()
            or db.query(Resume).order_by(Resume.date_created.desc()).first())
    if not base:
        raise HTTPException(400, "No resume saved. Add your base resume first.")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"tailored_resume": base.content, "ai_enabled": False,
                "suggestions": "Add ANTHROPIC_API_KEY to .env for AI tailoring."}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=4096,
            messages=[{"role": "user", "content":
                f"Tailor this resume to match the job description. Keep experience truthful, "
                f"reword bullet points to match keywords, be ATS-friendly. "
                f"Return ONLY the tailored resume.\n\nJOB:\n{payload.job_description}\n\nRESUME:\n{base.content}"}]
        )
        tailored = msg.content[0].text
        if payload.job_id:
            job = db.query(Job).filter(Job.id == payload.job_id).first()
            if job:
                job.tailored_resume = tailored; db.commit()
        return {"tailored_resume": tailored, "ai_enabled": True}
    except Exception as e:
        logger.error(f"Tailor error: {e}")
        return {"tailored_resume": base.content, "error": str(e), "ai_enabled": False}


# ══════════════════════════════════════════════════════════════════════════════
# COFFEE CHATS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/coffee-chats")
def list_chats(db: Session = Depends(get_db)):
    return [_chat_dict(c) for c in db.query(CoffeeChat).order_by(CoffeeChat.date_added.desc()).all()]

@app.post("/api/coffee-chats", status_code=201)
def create_chat(payload: CoffeeChatCreate, db: Session = Depends(get_db)):
    c = CoffeeChat(**payload.dict()); db.add(c); db.commit(); db.refresh(c)
    return _chat_dict(c)

@app.put("/api/coffee-chats/{chat_id}")
def update_chat(chat_id: int, payload: CoffeeChatUpdate, db: Session = Depends(get_db)):
    c = _get_or_404(db, CoffeeChat, chat_id)
    for k, v in payload.dict(exclude_none=True).items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return _chat_dict(c)

@app.delete("/api/coffee-chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    c = _get_or_404(db, CoffeeChat, chat_id)
    db.delete(c); db.commit()
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL OUTREACH
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/emails")
def list_emails(db: Session = Depends(get_db)):
    return [_email_dict(e) for e in db.query(EmailOutreach).order_by(EmailOutreach.date_sent.desc()).all()]

@app.post("/api/emails", status_code=201)
def create_email(payload: EmailCreate, db: Session = Depends(get_db)):
    e = EmailOutreach(**payload.dict()); db.add(e); db.commit(); db.refresh(e)
    return _email_dict(e)

@app.put("/api/emails/{email_id}")
def update_email(email_id: int, payload: EmailUpdate, db: Session = Depends(get_db)):
    e = _get_or_404(db, EmailOutreach, email_id)
    for k, v in payload.dict(exclude_none=True).items():
        setattr(e, k, v)
    db.commit(); db.refresh(e)
    return _email_dict(e)

@app.delete("/api/emails/{email_id}")
def delete_email(email_id: int, db: Session = Depends(get_db)):
    e = _get_or_404(db, EmailOutreach, email_id)
    db.delete(e); db.commit()
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/notifications")
def list_notifications(db: Session = Depends(get_db)):
    notifs = db.query(Notification).order_by(Notification.created_at.desc()).limit(100).all()
    return [_notif_dict(n) for n in notifs]

@app.get("/api/notifications/unread-count")
def unread_count(db: Session = Depends(get_db)):
    return {"count": db.query(Notification).filter(Notification.is_read == False).count()}

@app.put("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)):
    n = _get_or_404(db, Notification, notif_id)
    n.is_read = True; db.commit()
    return {"ok": True}

@app.put("/api/notifications/mark-all-read")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"ok": True}

@app.delete("/api/notifications/{notif_id}")
def delete_notification(notif_id: int, db: Session = Depends(get_db)):
    n = _get_or_404(db, Notification, notif_id)
    db.delete(n); db.commit()
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION ANSWERS (Question setup page)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/answers")
def list_answers(db: Session = Depends(get_db)):
    return [_answer_dict(a) for a in db.query(ApplicationAnswer).order_by(ApplicationAnswer.category).all()]

@app.put("/api/answers/{question_key}")
def upsert_answer(question_key: str, payload: AnswerUpsert, db: Session = Depends(get_db)):
    a = db.query(ApplicationAnswer).filter(ApplicationAnswer.question_key == question_key).first()
    if not a:
        raise HTTPException(404, f"Question '{question_key}' not found")
    a.answer = payload.answer
    a.updated_at = datetime.utcnow()
    db.commit()
    return _answer_dict(a)

@app.post("/api/answers/save-all")
def save_all_answers(payload: List[AnswerUpsert], db: Session = Depends(get_db)):
    for item in payload:
        a = db.query(ApplicationAnswer).filter(ApplicationAnswer.question_key == item.question_key).first()
        if a:
            a.answer = item.answer
            a.updated_at = datetime.utcnow()
    db.commit()
    return {"saved": len(payload)}


# ══════════════════════════════════════════════════════════════════════════════
# WORKDAY CREDENTIALS (Password vault)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/credentials")
def list_credentials(db: Session = Depends(get_db)):
    creds = db.query(WorkdayCredential).order_by(WorkdayCredential.company_name).all()
    return [_cred_dict(c) for c in creds]   # passwords NOT returned in list

@app.post("/api/credentials", status_code=201)
def create_credential(payload: CredentialCreate, db: Session = Depends(get_db)):
    cred = WorkdayCredential(
        company_name=payload.company_name,
        workday_domain=payload.workday_domain,
        email=payload.email,
        password_enc=encrypt_password(payload.password),
        notes=payload.notes,
    )
    db.add(cred); db.commit(); db.refresh(cred)
    return _cred_dict(cred)

@app.put("/api/credentials/{cred_id}")
def update_credential(cred_id: int, payload: CredentialUpdate, db: Session = Depends(get_db)):
    cred = _get_or_404(db, WorkdayCredential, cred_id)
    if payload.company_name is not None: cred.company_name = payload.company_name
    if payload.workday_domain is not None: cred.workday_domain = payload.workday_domain
    if payload.email is not None: cred.email = payload.email
    if payload.notes is not None: cred.notes = payload.notes
    if payload.password is not None:
        cred.password_enc = encrypt_password(payload.password)
    db.commit(); db.refresh(cred)
    return _cred_dict(cred)

@app.delete("/api/credentials/{cred_id}")
def delete_credential(cred_id: int, db: Session = Depends(get_db)):
    cred = _get_or_404(db, WorkdayCredential, cred_id)
    db.delete(cred); db.commit()
    return {"message": "Deleted"}

@app.post("/api/credentials/{cred_id}/test")
async def test_credential(cred_id: int, db: Session = Depends(get_db)):
    cred = _get_or_404(db, WorkdayCredential, cred_id)
    email, password = _resolve_cred(cred)
    if not email or not password:
        raise HTTPException(400, "Incomplete credentials")
    domain = cred.workday_domain or ""
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    result = await get_workday_status(domain, email, password)
    if result.get("wrong_password"):
        _add_notification(db, "error",
            f"Wrong password for {cred.company_name}",
            "The stored password is incorrect. Please update it.")
    elif result.get("success"):
        cred.last_used = datetime.utcnow(); db.commit()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    chats = db.query(CoffeeChat).all()
    emails = db.query(EmailOutreach).all()
    unread = db.query(Notification).filter(Notification.is_read == False).count()

    job_statuses = {}
    for j in jobs:
        job_statuses[j.status] = job_statuses.get(j.status, 0) + 1

    now = datetime.utcnow()
    return {
        "jobs": {
            "total": len(jobs),
            "by_status": job_statuses,
            "active": sum(1 for j in jobs if j.status in ["Applied", "Phone Screen", "Interview"]),
        },
        "coffee_chats": {
            "total": len(chats),
            "upcoming_follow_ups": sum(1 for c in chats if c.follow_up_date and c.follow_up_date >= now),
            "completed": sum(1 for c in chats if c.status == "Completed"),
        },
        "emails": {
            "total": len(emails),
            "pending_follow_up": sum(1 for e in emails if e.status in ["Sent", "Follow Up"]),
            "replied": sum(1 for e in emails if e.status == "Replied"),
        },
        "unread_notifications": unread,
    }


@app.get("/api/settings")
def get_settings():
    return {
        "workday_email": os.getenv("WORKDAY_EMAIL", ""),
        "workday_configured": bool(os.getenv("WORKDAY_EMAIL") and os.getenv("WORKDAY_PASSWORD")),
        "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db, model, id_):
    obj = db.query(model).filter(model.id == id_).first()
    if not obj:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj

def _fmt(dt): return dt.isoformat() if dt else None

def _add_notification(db, type_, title, message, job_id=None):
    n = Notification(type=type_, title=title, message=message, job_id=job_id)
    db.add(n); db.commit()

def _find_credential(db, url: str) -> Optional[WorkdayCredential]:
    """Find a stored credential matching the URL's domain."""
    if not url:
        return None
    domain = _extract_domain(url)
    creds = db.query(WorkdayCredential).all()
    for c in creds:
        if c.workday_domain and (c.workday_domain in url or domain in (c.workday_domain or "")):
            return c
    return None

def _resolve_cred(cred: Optional[WorkdayCredential]):
    if not cred:
        return "", ""
    return cred.email or "", decrypt_password(cred.password_enc or "")

def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""

def _job_dict(j: Job):
    return {"id": j.id, "company": j.company, "title": j.title, "job_url": j.job_url,
            "workday_url": j.workday_url, "status": j.status, "date_added": _fmt(j.date_added),
            "date_applied": _fmt(j.date_applied), "last_status_check": _fmt(j.last_status_check),
            "job_description": j.job_description, "tailored_resume": j.tailored_resume,
            "notes": j.notes, "salary_range": j.salary_range, "location": j.location, "source": j.source}

def _chat_dict(c: CoffeeChat):
    return {"id": c.id, "person_name": c.person_name, "company": c.company, "role": c.role,
            "linkedin_url": c.linkedin_url, "email": c.email, "status": c.status,
            "date_added": _fmt(c.date_added), "date_reached_out": _fmt(c.date_reached_out),
            "date_meeting": _fmt(c.date_meeting), "follow_up_date": _fmt(c.follow_up_date),
            "notes": c.notes, "next_action": c.next_action, "meeting_notes": c.meeting_notes}

def _email_dict(e: EmailOutreach):
    return {"id": e.id, "recipient_name": e.recipient_name, "recipient_email": e.recipient_email,
            "company": e.company, "subject": e.subject, "status": e.status,
            "date_sent": _fmt(e.date_sent), "follow_up_date": _fmt(e.follow_up_date),
            "notes": e.notes, "email_body": e.email_body}

def _notif_dict(n: Notification):
    return {"id": n.id, "type": n.type, "title": n.title, "message": n.message,
            "job_id": n.job_id, "is_read": n.is_read, "created_at": _fmt(n.created_at)}

def _answer_dict(a: ApplicationAnswer):
    return {"id": a.id, "question_key": a.question_key, "question_label": a.question_label,
            "answer": a.answer, "category": a.category, "updated_at": _fmt(a.updated_at)}

def _cred_dict(c: WorkdayCredential):
    return {"id": c.id, "company_name": c.company_name, "workday_domain": c.workday_domain,
            "email": c.email, "notes": c.notes, "last_used": _fmt(c.last_used),
            "created_at": _fmt(c.created_at)}   # password_enc intentionally omitted


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
