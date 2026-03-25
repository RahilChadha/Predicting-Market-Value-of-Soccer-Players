"""
Workday automation using Playwright.
- Tries existing account password
- Creates new account if no account exists
- Auto-fills application form from saved answers
- Reports wrong_password / no_account so dashboard can notify user
"""

import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


# ── Field map: question_key → list of Workday selectors to try ────────────────
FIELD_MAP: Dict[str, list] = {
    "first_name": [
        "[data-automation-id='legalNameSection_firstName']",
        "input[name='firstName']", "input[placeholder*='First']",
    ],
    "last_name": [
        "[data-automation-id='legalNameSection_lastName']",
        "input[name='lastName']", "input[placeholder*='Last']",
    ],
    "email": [
        "[data-automation-id='email']", "input[type='email']", "input[name='email']",
    ],
    "phone": [
        "[data-automation-id='phone-number']", "input[name='phone']",
        "input[placeholder*='Phone']", "input[type='tel']",
    ],
    "address_line1": [
        "[data-automation-id='addressSection_addressLine1']",
        "input[name='addressLine1']", "input[placeholder*='Address']",
    ],
    "city": [
        "[data-automation-id='addressSection_city']",
        "input[name='city']", "input[placeholder*='City']",
    ],
    "state": [
        "[data-automation-id='addressSection_regionCode']",
        "select[name='state']", "input[placeholder*='State']",
    ],
    "zip_code": [
        "[data-automation-id='addressSection_postalCode']",
        "input[name='postalCode']", "input[placeholder*='ZIP']",
    ],
    "linkedin_url": [
        "input[placeholder*='LinkedIn']", "input[name='linkedinUrl']",
    ],
    "github_url": [
        "input[placeholder*='GitHub']", "input[placeholder*='Portfolio']",
    ],
    "desired_salary": [
        "input[placeholder*='Salary']", "input[placeholder*='salary']",
        "input[name='desiredSalary']",
    ],
}


# ── Login helper ──────────────────────────────────────────────────────────────

async def _do_login(page, email: str, password: str) -> dict:
    """
    Attempt to log into whatever login form is on the current page.
    Returns {"success": True} or {"wrong_password": True} or {"no_account": True}.
    """
    try:
        # Fill email
        for sel in ["[data-automation-id='email']", "input[type='email']", "input[name='email']", "#email"]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(email)
                break

        # Click Next if present
        for sel in ["[data-automation-id='next']", "button:has-text('Next')", "#next"]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(1500)
                break

        # Check for "create account" signals after entering email
        body_text = await page.inner_text("body")
        body_lower = body_text.lower()
        if any(x in body_lower for x in ["create account", "sign up", "register", "no account found"]):
            return {"no_account": True}

        # Fill password
        for sel in ["[data-automation-id='password']", "input[type='password']", "input[name='password']", "#password"]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(password)
                break

        # Submit
        for sel in ["[data-automation-id='signIn']", "button[type='submit']", "button:has-text('Sign In')", "input[type='submit']"]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(3000)
                break

        # Check result
        body_text = await page.inner_text("body")
        body_lower = body_text.lower()

        wrong_password_signals = [
            "incorrect password", "invalid password", "wrong password",
            "authentication failed", "invalid credentials", "login failed",
            "password is incorrect", "unable to sign in",
        ]
        if any(x in body_lower for x in wrong_password_signals):
            return {"wrong_password": True}

        return {"success": True}

    except Exception as e:
        logger.error(f"Login error: {e}")
        return {"error": str(e)}


async def _create_account(page, email: str, password: str, answers: dict):
    """Attempt to create a new Workday account using the stored answers."""
    try:
        # Look for "Create Account" button/link
        for sel in [
            "a:has-text('Create Account')", "button:has-text('Create Account')",
            "a:has-text('Sign Up')", "button:has-text('Sign Up')",
            "[data-automation-id='createAccount']",
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(2000)
                break

        # Fill registration form
        for sel in ["[data-automation-id='email']", "input[type='email']"]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(email)
                break

        # Password fields
        for sel in ["[data-automation-id='password']", "input[name='password']", "input[type='password']"]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(password)
                break

        for sel in ["[data-automation-id='verifyPassword']", "input[name='confirmPassword']"]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(password)
                break

        # Name fields from saved answers
        first = answers.get("first_name", "")
        last = answers.get("last_name", "")
        for sel in FIELD_MAP.get("first_name", []):
            el = await page.query_selector(sel)
            if el and first:
                await el.fill(first)
                break
        for sel in FIELD_MAP.get("last_name", []):
            el = await page.query_selector(sel)
            if el and last:
                await el.fill(last)
                break

        # Submit
        for sel in ["button[type='submit']", "button:has-text('Create')", "button:has-text('Register')"]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(3000)
                break

    except Exception as e:
        logger.error(f"Create account error: {e}")


async def _autofill_application(page, answers: dict):
    """Auto-fill visible application form fields using saved answers."""
    for key, selectors in FIELD_MAP.items():
        value = answers.get(key, "")
        if not value:
            continue
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    tag = await el.get_attribute("tagName") or ""
                    if tag.lower() == "select":
                        await el.select_option(label=value)
                    else:
                        await el.fill(value)
                    break
            except Exception:
                continue

    # Handle radio/checkbox questions (work auth, sponsorship etc.)
    radio_map = {
        "work_authorized_us": {"yes": "Yes", "no": "No"},
        "sponsorship_required": {"yes": "Yes", "no": "No"},
        "willing_to_relocate": {"yes": "Yes", "no": "No"},
    }
    for key, option_map in radio_map.items():
        answer = answers.get(key, "").lower()
        if not answer:
            continue
        label_text = option_map.get(answer, answer)
        try:
            radio = await page.query_selector(f"input[type='radio'][value='{label_text}']")
            if not radio:
                radio = await page.query_selector(f"label:has-text('{label_text}') input[type='radio']")
            if radio:
                await radio.click()
        except Exception:
            continue


# ── Public API ────────────────────────────────────────────────────────────────

async def get_workday_status(workday_url: str, email: str, password: str) -> dict:
    """Log into a Workday portal and check application status."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                await page.goto(workday_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Click Sign In if on landing page
                for sel in ["text=Sign In", "a:has-text('Sign In')", "button:has-text('Sign In')"]:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await page.wait_for_timeout(1500)
                        break

                login_result = await _do_login(page, email, password)

                if login_result.get("wrong_password"):
                    return {"success": False, "wrong_password": True, "status": "Login Failed",
                            "checked_at": datetime.utcnow().isoformat()}

                if login_result.get("no_account"):
                    return {"success": False, "no_account": True, "status": "No Account",
                            "checked_at": datetime.utcnow().isoformat()}

                body = await page.inner_text("body")
                status = _parse_status(body)
                return {"success": True, "status": status, "checked_at": datetime.utcnow().isoformat()}

            except Exception as e:
                logger.error(f"Status check error: {e}")
                return {"success": False, "error": str(e), "status": "Check Failed"}
            finally:
                await browser.close()

    except ImportError:
        return {"success": False, "error": "Run: pip install playwright && playwright install chromium",
                "status": "Setup Required"}


async def apply_to_job(job_url: str, email: str, password: str,
                       answers: dict, resume_text: str = "") -> dict:
    """
    Apply to a job:
    1. Try to sign in with stored password
    2. If no account → create one
    3. If wrong password → notify caller
    4. Auto-fill form from saved answers
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Visible for user review
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                await page.goto(job_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Click Apply button
                for sel in [
                    "[data-automation-id='applyNowButton']",
                    "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                    "a:has-text('Apply')", "button:has-text('Apply')",
                ]:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await page.wait_for_timeout(3000)
                        break

                current_url = page.url
                body_text = await page.inner_text("body")

                # If redirected to login
                if "login" in current_url or "signin" in current_url or "sign-in" in current_url \
                        or "sign in" in body_text.lower():

                    login_result = await _do_login(page, email, password)

                    if login_result.get("wrong_password"):
                        await browser.close()
                        return {"success": False, "wrong_password": True,
                                "status": "Wrong password — update it in Job Setup > Passwords"}

                    if login_result.get("no_account"):
                        await _create_account(page, email, password, answers)
                        await page.wait_for_timeout(2000)
                        # Re-navigate to job after account creation
                        await page.goto(job_url, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(2000)
                        # Try clicking Apply again
                        for sel in ["[data-automation-id='applyNowButton']", "button:has-text('Apply')"]:
                            el = await page.query_selector(sel)
                            if el:
                                await el.click()
                                await page.wait_for_timeout(3000)
                                break
                        await _autofill_application(page, answers)
                        await page.wait_for_timeout(5000)
                        return {"success": True, "no_account": True,
                                "status": "New account created — review & submit the form",
                                "applied_at": datetime.utcnow().isoformat()}

                # Auto-fill form
                await _autofill_application(page, answers)
                await page.wait_for_timeout(5000)

                return {"success": True, "status": "Application started — review & submit the form",
                        "applied_at": datetime.utcnow().isoformat()}

            except Exception as e:
                logger.error(f"Apply error: {e}")
                return {"success": False, "error": str(e), "status": "Failed"}
            # NOTE: browser is intentionally left open for user to finish form

    except ImportError:
        return {"success": False, "error": "Run: pip install playwright && playwright install chromium",
                "status": "Setup Required"}


def _parse_status(page_text: str) -> str:
    t = page_text.lower()
    checks = [
        ("under review", "Under Review"),
        ("interview", "Interview Scheduled"),
        ("phone screen", "Phone Screen"),
        ("offer", "Offer Extended"),
        ("not selected", "Rejected"),
        ("rejected", "Rejected"),
        ("hired", "Hired"),
        ("withdrawn", "Withdrawn"),
        ("submitted", "Applied"),
        ("application received", "Applied"),
        ("in progress", "In Progress"),
    ]
    for keyword, status in checks:
        if keyword in t:
            return status
    return "Applied"
