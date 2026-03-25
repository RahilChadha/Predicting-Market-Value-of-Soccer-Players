"""
Workday automation using Playwright.
Logs in with stored credentials and checks application statuses.

SECURITY NOTE: Credentials are loaded from environment variables only.
Never hardcode credentials in source code.
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


async def get_workday_status(workday_url: str, email: str, password: str) -> dict:
    """
    Log into a Workday portal and check application status.
    Returns dict with status and any available details.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(workday_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Try to find sign-in button or email field
                sign_in_selectors = [
                    "text=Sign In",
                    "text=Log In",
                    "[data-automation-id='signInWithEmail']",
                    "a[href*='login']",
                    "button:has-text('Sign In')"
                ]

                for selector in sign_in_selectors:
                    try:
                        el = await page.query_selector(selector)
                        if el:
                            await el.click()
                            await page.wait_for_timeout(1500)
                            break
                    except Exception:
                        continue

                # Fill email
                email_selectors = [
                    "[data-automation-id='email']",
                    "input[type='email']",
                    "input[name='email']",
                    "#email",
                ]
                for sel in email_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.fill(email)
                            break
                    except Exception:
                        continue

                # Click next if needed
                next_selectors = ["[data-automation-id='next']", "button:has-text('Next')", "#next"]
                for sel in next_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.click()
                            await page.wait_for_timeout(1500)
                            break
                    except Exception:
                        continue

                # Fill password
                pwd_selectors = [
                    "[data-automation-id='password']",
                    "input[type='password']",
                    "input[name='password']",
                    "#password",
                ]
                for sel in pwd_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.fill(password)
                            break
                    except Exception:
                        continue

                # Submit login
                submit_selectors = [
                    "[data-automation-id='signIn']",
                    "button[type='submit']",
                    "button:has-text('Sign In')",
                    "input[type='submit']",
                ]
                for sel in submit_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue

                # Check for application status on page
                status_text = await page.inner_text("body")
                status = _parse_workday_status(status_text)

                return {
                    "success": True,
                    "status": status,
                    "checked_at": datetime.utcnow().isoformat(),
                    "url": workday_url,
                }

            except Exception as e:
                logger.error(f"Error checking Workday status: {e}")
                return {"success": False, "error": str(e), "status": "Check Failed"}
            finally:
                await browser.close()

    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "status": "Setup Required",
        }


def _parse_workday_status(page_text: str) -> str:
    """Parse common Workday status indicators from page text."""
    text_lower = page_text.lower()
    status_keywords = {
        "under review": "Under Review",
        "interview": "Interview Scheduled",
        "phone screen": "Phone Screen",
        "offer": "Offer Extended",
        "rejected": "Rejected",
        "not selected": "Rejected",
        "hired": "Hired",
        "withdrawn": "Withdrawn",
        "submitted": "Applied",
        "application received": "Applied",
        "in progress": "In Progress",
    }
    for keyword, status in status_keywords.items():
        if keyword in text_lower:
            return status
    return "Applied"


async def apply_to_job(job_url: str, email: str, password: str, resume_text: str = "") -> dict:
    """
    Attempt to apply to a job on Workday.
    Returns success status and any notes.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Visible for manual review
            page = await browser.new_page()

            await page.goto(job_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Click Apply button
            apply_selectors = [
                "[data-automation-id='applyNowButton']",
                "a:has-text('Apply')",
                "button:has-text('Apply Now')",
                "button:has-text('Apply')",
            ]
            applied = False
            for sel in apply_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await page.wait_for_timeout(3000)
                        applied = True
                        break
                except Exception:
                    continue

            if not applied:
                return {"success": False, "error": "Could not find Apply button", "status": "Manual Required"}

            # Handle login if redirected
            current_url = page.url
            if "login" in current_url or "signin" in current_url:
                await _login_workday(page, email, password)

            # Keep browser open for manual review of application form
            await page.wait_for_timeout(5000)

            return {
                "success": True,
                "status": "Application Started - Complete form manually",
                "applied_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Error applying to job: {e}")
        return {"success": False, "error": str(e), "status": "Failed"}


async def _login_workday(page, email: str, password: str):
    """Helper to log into Workday during application flow."""
    try:
        email_el = await page.query_selector("input[type='email'], [data-automation-id='email']")
        if email_el:
            await email_el.fill(email)

        next_el = await page.query_selector("[data-automation-id='next'], button:has-text('Next')")
        if next_el:
            await next_el.click()
            await page.wait_for_timeout(1500)

        pwd_el = await page.query_selector("input[type='password'], [data-automation-id='password']")
        if pwd_el:
            await pwd_el.fill(password)

        submit_el = await page.query_selector("[data-automation-id='signIn'], button[type='submit']")
        if submit_el:
            await submit_el.click()
            await page.wait_for_timeout(3000)
    except Exception as e:
        logger.error(f"Login helper error: {e}")
