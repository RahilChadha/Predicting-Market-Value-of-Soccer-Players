"""
Job Tracking Dashboard - FastAPI Backend
Tracks job applications, coffee chats, and email outreach.
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_db, Job, CoffeeChat, EmailOutreach, Resume
from automation.workday import get_workday_status, apply_to_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title="Job Tracking Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

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


class ApplyRequest(BaseModel):
    job_id: int


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


# ── Jobs API ──────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.date_added.desc()).all()
    return [_job_to_dict(j) for j in jobs]


@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = Job(**payload.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@app.put("/api/jobs/{job_id}")
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in payload.dict(exclude_none=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Deleted"}


@app.post("/api/jobs/{job_id}/check-status")
async def check_job_status(job_id: int, db: Session = Depends(get_db)):
    """Check Workday status for a specific job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.workday_url:
        raise HTTPException(status_code=400, detail="No Workday URL set for this job")

    email = os.getenv("WORKDAY_EMAIL", "")
    password = os.getenv("WORKDAY_PASSWORD", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Workday credentials not configured in .env file")

    result = await get_workday_status(job.workday_url, email, password)
    if result.get("success"):
        job.status = result["status"]
        job.last_status_check = datetime.utcnow()
        db.commit()
    return result


@app.post("/api/jobs/{job_id}/apply")
async def apply_job(job_id: int, db: Session = Depends(get_db)):
    """Launch Workday automation to apply to a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    url = job.workday_url or job.job_url
    if not url:
        raise HTTPException(status_code=400, detail="No job URL configured")

    email = os.getenv("WORKDAY_EMAIL", "")
    password = os.getenv("WORKDAY_PASSWORD", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Workday credentials not configured in .env file")

    result = await apply_to_job(url, email, password, job.tailored_resume or "")
    if result.get("success"):
        job.status = "Applied"
        job.date_applied = datetime.utcnow()
        db.commit()
    return result


@app.post("/api/jobs/check-all-statuses")
async def check_all_statuses(db: Session = Depends(get_db)):
    """Check Workday status for all applied jobs (weekly refresh)."""
    email = os.getenv("WORKDAY_EMAIL", "")
    password = os.getenv("WORKDAY_PASSWORD", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Workday credentials not configured")

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    jobs = db.query(Job).filter(
        Job.workday_url.isnot(None),
        Job.status.notin_(["Offer", "Rejected", "Withdrawn", "To Apply"]),
    ).all()

    results = []
    for job in jobs:
        try:
            result = await get_workday_status(job.workday_url, email, password)
            if result.get("success"):
                job.status = result["status"]
                job.last_status_check = datetime.utcnow()
            results.append({"job_id": job.id, "company": job.company, "title": job.title, **result})
        except Exception as e:
            results.append({"job_id": job.id, "error": str(e)})

    db.commit()
    return {"checked": len(results), "results": results}


# ── Resume API ────────────────────────────────────────────────────────────────

@app.get("/api/resumes")
def list_resumes(db: Session = Depends(get_db)):
    resumes = db.query(Resume).order_by(Resume.date_created.desc()).all()
    return [{"id": r.id, "name": r.name, "is_base": r.is_base, "date_created": r.date_created} for r in resumes]


@app.post("/api/resumes", status_code=201)
def create_resume(payload: ResumeCreate, db: Session = Depends(get_db)):
    if payload.is_base:
        # Only one base resume at a time
        db.query(Resume).filter(Resume.is_base == True).update({"is_base": False})
    resume = Resume(**payload.dict())
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return {"id": resume.id, "name": resume.name, "is_base": resume.is_base}


@app.get("/api/resumes/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"id": resume.id, "name": resume.name, "content": resume.content, "is_base": resume.is_base}


@app.post("/api/resumes/tailor")
async def tailor_resume(payload: TailorRequest, db: Session = Depends(get_db)):
    """Use Claude AI to tailor resume to a job description."""
    base_resume = db.query(Resume).filter(Resume.is_base == True).first()
    if not base_resume:
        base_resume = db.query(Resume).order_by(Resume.date_created.desc()).first()
    if not base_resume:
        raise HTTPException(status_code=400, detail="No resume uploaded. Add your base resume first.")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "tailored_resume": base_resume.content,
            "suggestions": "Add ANTHROPIC_API_KEY to .env to enable AI tailoring.",
            "ai_enabled": False,
        }

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""You are an expert resume writer. Tailor the following resume to match the job description.

INSTRUCTIONS:
1. Keep the same overall structure and truthful experience
2. Reword bullet points to match keywords from the job description
3. Prioritize relevant skills and experiences
4. Keep it concise and ATS-friendly
5. Return ONLY the tailored resume text, nothing else

JOB DESCRIPTION:
{payload.job_description}

BASE RESUME:
{base_resume.content}

Return the tailored resume:"""
            }]
        )

        tailored = message.content[0].text

        # Save to job if job_id provided
        if payload.job_id:
            job = db.query(Job).filter(Job.id == payload.job_id).first()
            if job:
                job.tailored_resume = tailored
                db.commit()

        return {"tailored_resume": tailored, "ai_enabled": True}

    except Exception as e:
        logger.error(f"Resume tailoring error: {e}")
        return {"tailored_resume": base_resume.content, "error": str(e), "ai_enabled": False}


# ── Coffee Chats API ──────────────────────────────────────────────────────────

@app.get("/api/coffee-chats")
def list_coffee_chats(db: Session = Depends(get_db)):
    chats = db.query(CoffeeChat).order_by(CoffeeChat.date_added.desc()).all()
    return [_chat_to_dict(c) for c in chats]


@app.post("/api/coffee-chats", status_code=201)
def create_coffee_chat(payload: CoffeeChatCreate, db: Session = Depends(get_db)):
    chat = CoffeeChat(**payload.dict())
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return _chat_to_dict(chat)


@app.put("/api/coffee-chats/{chat_id}")
def update_coffee_chat(chat_id: int, payload: CoffeeChatUpdate, db: Session = Depends(get_db)):
    chat = db.query(CoffeeChat).filter(CoffeeChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Coffee chat not found")
    for field, value in payload.dict(exclude_none=True).items():
        setattr(chat, field, value)
    db.commit()
    db.refresh(chat)
    return _chat_to_dict(chat)


@app.delete("/api/coffee-chats/{chat_id}")
def delete_coffee_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = db.query(CoffeeChat).filter(CoffeeChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(chat)
    db.commit()
    return {"message": "Deleted"}


# ── Email Outreach API ────────────────────────────────────────────────────────

@app.get("/api/emails")
def list_emails(db: Session = Depends(get_db)):
    emails = db.query(EmailOutreach).order_by(EmailOutreach.date_sent.desc()).all()
    return [_email_to_dict(e) for e in emails]


@app.post("/api/emails", status_code=201)
def create_email(payload: EmailCreate, db: Session = Depends(get_db)):
    email = EmailOutreach(**payload.dict())
    db.add(email)
    db.commit()
    db.refresh(email)
    return _email_to_dict(email)


@app.put("/api/emails/{email_id}")
def update_email(email_id: int, payload: EmailUpdate, db: Session = Depends(get_db)):
    email = db.query(EmailOutreach).filter(EmailOutreach.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    for field, value in payload.dict(exclude_none=True).items():
        setattr(email, field, value)
    db.commit()
    db.refresh(email)
    return _email_to_dict(email)


@app.delete("/api/emails/{email_id}")
def delete_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(EmailOutreach).filter(EmailOutreach.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(email)
    db.commit()
    return {"message": "Deleted"}


# ── Stats API ─────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    chats = db.query(CoffeeChat).all()
    emails = db.query(EmailOutreach).all()

    job_statuses = {}
    for j in jobs:
        job_statuses[j.status] = job_statuses.get(j.status, 0) + 1

    follow_up_jobs = [j for j in jobs if j.status in ["Applied", "Phone Screen", "Interview"]]
    upcoming_chats = [c for c in chats if c.follow_up_date and c.follow_up_date >= datetime.utcnow()]
    pending_emails = [e for e in emails if e.status in ["Sent", "Follow Up"]]

    return {
        "jobs": {
            "total": len(jobs),
            "by_status": job_statuses,
            "active": len(follow_up_jobs),
        },
        "coffee_chats": {
            "total": len(chats),
            "upcoming_follow_ups": len(upcoming_chats),
            "completed": sum(1 for c in chats if c.status == "Completed"),
        },
        "emails": {
            "total": len(emails),
            "pending_follow_up": len(pending_emails),
            "replied": sum(1 for e in emails if e.status == "Replied"),
        },
    }


# ── Settings API ──────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return {
        "workday_email": os.getenv("WORKDAY_EMAIL", ""),
        "workday_configured": bool(os.getenv("WORKDAY_EMAIL") and os.getenv("WORKDAY_PASSWORD")),
        "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(dt):
    return dt.isoformat() if dt else None


def _job_to_dict(j: Job):
    return {
        "id": j.id, "company": j.company, "title": j.title,
        "job_url": j.job_url, "workday_url": j.workday_url,
        "status": j.status, "date_added": _fmt(j.date_added),
        "date_applied": _fmt(j.date_applied), "last_status_check": _fmt(j.last_status_check),
        "job_description": j.job_description, "tailored_resume": j.tailored_resume,
        "notes": j.notes, "salary_range": j.salary_range,
        "location": j.location, "source": j.source,
    }


def _chat_to_dict(c: CoffeeChat):
    return {
        "id": c.id, "person_name": c.person_name, "company": c.company,
        "role": c.role, "linkedin_url": c.linkedin_url, "email": c.email,
        "status": c.status, "date_added": _fmt(c.date_added),
        "date_reached_out": _fmt(c.date_reached_out), "date_meeting": _fmt(c.date_meeting),
        "follow_up_date": _fmt(c.follow_up_date), "notes": c.notes,
        "next_action": c.next_action, "meeting_notes": c.meeting_notes,
    }


def _email_to_dict(e: EmailOutreach):
    return {
        "id": e.id, "recipient_name": e.recipient_name, "recipient_email": e.recipient_email,
        "company": e.company, "subject": e.subject, "status": e.status,
        "date_sent": _fmt(e.date_sent), "follow_up_date": _fmt(e.follow_up_date),
        "notes": e.notes, "email_body": e.email_body,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
