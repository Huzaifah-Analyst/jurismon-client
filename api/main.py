"""JurisMon Production FastAPI Backend.

Sub-Task 4.4:
Provides:
- Instant Full-Text Search API across snapshots & statutory diff deltas
- PayPal Subscriptions & Webhook Processing Engine
- Secure Admin Authentication & Subscriber Management
- Serves Minimalist Search UI & Admin Dashboard
"""

import os
import sys
import json
import time
import shutil
import subprocess
import logging
import asyncio
from collections import defaultdict
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException, Query, Depends, status, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.repository import Repository
import secrets
from datetime import datetime, timezone, timedelta
from api.auth import (
    create_access_token,
    require_admin,
    authenticate_admin,
    ADMIN_EMAIL,
    get_password_hash,
    verify_password,
    create_customer_token,
    get_current_customer_optional,
    require_customer,
    is_admin_token,
)
from api.payments.paypal_provider import PayPalProvider
from notifications.mailer import Mailer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jurismon.api")
_subscription_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

app = FastAPI(
    title="JurisMon Regulatory Drift API",
    description="Statutory Zoning & Municipal Regulatory Delta Engine",
    version="1.0.0",
)

# A wildcard origin combined with credentials lets any site issue authenticated
# requests against the admin API, so origins are read from the environment.
_default_origins = "http://localhost:8000,http://127.0.0.1:8000"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

repo = Repository()
paypal_provider = PayPalProvider()
mailer = Mailer()


def _load_plan_catalogue() -> Dict[str, Any]:
    """Reads config/plans.json, the single source of truth for what we sell.

    The PayPal plan ids here must match the live plans; scripts/verify_plans.py
    checks that, because a mismatch silently bills the wrong amount.
    """
    path = os.path.join(os.path.dirname(__file__), "..", "config", "plans.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.error(f"Could not read plan catalogue: {exc}")
        return {"currency": "USD", "trial_days": 0, "plans": []}


PLAN_CATALOGUE = _load_plan_catalogue()


def _monthly_value(plan: Dict[str, Any]) -> float:
    """Normalises a plan's price to a monthly figure so MRR is comparable."""
    price = float(plan.get("price", 0))
    return price / 12.0 if plan.get("interval") == "year" else price

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


class LoginRequest(BaseModel):
    email: str
    password: str


class CustomerRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class CustomerLoginRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


# ==========================================
# PUBLIC SEARCH & FRONTEND ROUTES
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_search_page():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "<h1>JurisMon Regulatory Monitor API is running.</h1>"


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_page():
    admin_path = os.path.join(frontend_dir, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return "<h1>JurisMon Admin Panel</h1>"


@app.get("/terms", response_class=HTMLResponse)
async def serve_terms_page():
    terms_path = os.path.join(frontend_dir, "terms.html")
    if os.path.exists(terms_path):
        return FileResponse(terms_path)
    return "<h1>JurisMon Terms of Service</h1>"


@app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy_page():
    privacy_path = os.path.join(frontend_dir, "privacy.html")
    if os.path.exists(privacy_path):
        return FileResponse(privacy_path)
    return "<h1>JurisMon Privacy Policy</h1>"


@app.get("/account", response_class=HTMLResponse)
async def serve_account_page():
    account_path = os.path.join(frontend_dir, "account.html")
    if os.path.exists(account_path):
        return FileResponse(account_path)
    return "<h1>JurisMon Customer Account</h1>"


@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    favicon_path = os.path.join(frontend_dir, "assets", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(status_code=404)


@app.get("/site.webmanifest", include_in_schema=False)
async def serve_site_webmanifest():
    manifest_path = os.path.join(frontend_dir, "assets", "site.webmanifest")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return Response(status_code=404)


@app.get("/robots.txt", response_class=PlainTextResponse)
async def serve_robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "Sitemap: https://jurismon.com/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml")
async def serve_sitemap_xml():
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        "    <loc>https://jurismon.com/</loc>\n"
        "    <changefreq>daily</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "  <url>\n"
        "    <loc>https://jurismon.com/terms</loc>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.5</priority>\n"
        "  </url>\n"
        "  <url>\n"
        "    <loc>https://jurismon.com/privacy</loc>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.5</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    return Response(content=content, media_type="application/xml")


def format_result_items(search_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Maps internal diffs and snapshots into the unified frontend card contract."""
    items = []
    # Process Diffs
    for d in search_data.get("diffs", []):
        payload = d.get("diff_payload", {})
        doc_info = d.get("documents", {})
        doc_title = doc_info.get("title", "Municipal Document")
        doc_url = doc_info.get("pdf_url", "#")
        source_name = doc_info.get("source_name") or "Municipal Regulatory Authority"
        created_at = d.get("generated_at") or "2026-09-27T00:00:00Z"

        for mod in payload.get("modified", []):
            sec = mod.get("identifier") or mod.get("section_number") or "Section"
            deltas = mod.get("word_deltas", [])
            segments = []
            for w in deltas:
                op = "eq"
                if w.get("operation") == "insert":
                    op = "add"
                elif w.get("operation") == "delete":
                    op = "del"
                segments.append([op, w.get("text", "")])
            
            items.append({
                "id": f"diff-{d.get('id')}-{sec}".replace(" ", "-"),
                "type": "diff",
                "entity": source_name,
                "doc": doc_title,
                "section": sec,
                "segments": segments if segments else [["eq", mod.get("new_text", "")]],
                "full": mod.get("new_text", ""),
                "url": doc_url,
                "ts": created_at,
            })

        for add in payload.get("added", []):
            sec = add.get("identifier") or add.get("section_number") or "Section"
            items.append({
                "id": f"add-{d.get('id')}-{sec}".replace(" ", "-"),
                "type": "diff",
                "entity": source_name,
                "doc": doc_title,
                "section": sec,
                "segments": [["add", add.get("text", "")]],
                "full": add.get("text", ""),
                "url": doc_url,
                "ts": created_at,
            })

        for rem in payload.get("removed", []):
            sec = rem.get("identifier") or rem.get("section_number") or "Section"
            items.append({
                "id": f"del-{d.get('id')}-{sec}".replace(" ", "-"),
                "type": "diff",
                "entity": source_name,
                "doc": doc_title,
                "section": sec,
                "segments": [["del", rem.get("text", "")]],
                "full": rem.get("text", ""),
                "url": doc_url,
                "ts": created_at,
            })

    # Process Snapshots
    for s in search_data.get("snapshots", []):
        doc_info = s.get("documents", {})
        doc_title = doc_info.get("title", "Municipal Document")
        doc_url = doc_info.get("pdf_url", "#")
        source_name = doc_info.get("source_name") or "Municipal Regulatory Authority"
        created_at = s.get("crawled_at") or "2026-09-27T00:00:00Z"
        clean_text = s.get("cleaned_text", "")
        preview = clean_text[:240] + "..." if len(clean_text) > 240 else clean_text

        items.append({
            "id": f"snap-{s.get('id')}".replace(" ", "-"),
            "type": "snapshot",
            "entity": source_name,
            "doc": doc_title,
            "section": f"Snapshot v{s.get('version', 1)}",
            "text": preview,
            "full": clean_text,
            "url": doc_url,
            "ts": created_at,
        })

    return items


@app.get("/api/search")
async def search_endpoint(
    q: str = Query(default="", description="Search keyword or section number"),
    auth_user: Optional[dict] = Depends(get_current_customer_optional),
):
    """Instant search querying statutory text snapshots and calculated diffs."""
    results = repo.search_snapshots_and_diffs(query=q)
    items = format_result_items(results)

    has_access = False
    access_status = {"has_access": False, "reason": "unauthenticated"}

    if auth_user:
        if is_admin_token(auth_user):
            has_access = True
            access_status = {"has_access": True, "reason": "admin"}
        else:
            access_status = repo.get_user_access_status(auth_user.get("user_id") or auth_user.get("sub"))
            has_access = bool(access_status.get("has_access"))

    total_snaps = results.get("total_snapshots")
    if total_snaps is None:
        total_snaps = len(results.get("snapshots", []))
    total_dfs = results.get("total_diffs")
    if total_dfs is None:
        total_dfs = len(results.get("diffs", []))

    if not has_access:
        teaser_items = items[:2]
        for item in teaser_items:
            item["full"] = (
                "Full statutory text and clause delta history are locked. "
                "Sign up for a 14-day free trial or subscribe to JurisMon Professional ($49/mo) to unlock complete access."
            )
            item["is_locked"] = True
        return {
            "query": q,
            "total_snapshots": total_snaps,
            "total_diffs": total_dfs,
            "results": results,
            "items": teaser_items,
            "is_gated": True,
            "gate_reason": access_status.get("reason", "unauthenticated"),
            "access": access_status,
        }

    return {
        "query": q,
        "total_snapshots": total_snaps,
        "total_diffs": total_dfs,
        "results": results,
        "items": items,
        "is_gated": False,
        "access": access_status,
    }


@app.get("/api/sources")
async def list_sources(
    filter_type: Optional[str] = Query(default="all"),
    auth_user: Optional[Dict[str, Any]] = Depends(get_current_customer_optional),
):
    """Lists municipal sources with real-world audit categorization."""
    all_sources = repo.get_all_sources()
    total = len(all_sources)

    if not is_admin_token(auth_user):
        return {
            "count": total,
            "total_configured": total,
        }

    # health_status is authoritative; falling back to is_active counted every
    # parked source as operational.
    operational = [s for s in all_sources if s.get("health_status") == "operational"]
    cloudflare = [s for s in all_sources if s.get("health_status") == "cloudflare_blocked"]
    dead_links = [s for s in all_sources if s.get("health_status") == "dead_link"]

    return {
        "count": total,
        "total_configured": total,
        "operational_count": len(operational),
        "cloudflare_count": len(cloudflare),
        "dead_links_count": len(dead_links),
        "sources": all_sources,
    }


# ==========================================
# PAYPAL SUBSCRIPTIONS & WEBHOOK ROUTE
# ==========================================

class SubscribeRequest(BaseModel):
    plan: str
    email: Optional[str] = None


@app.get("/api/plans")
async def public_plans():
    """The plan catalogue, for the pricing section on the public page."""
    return {
        "currency": PLAN_CATALOGUE.get("currency", "USD"),
        "trial_days": PLAN_CATALOGUE.get("trial_days", 0),
        "plans": [
            {
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "interval": p["interval"],
            }
            for p in PLAN_CATALOGUE.get("plans", [])
            if p.get("is_active", True)
        ],
    }


@app.post("/api/subscriptions/create")
async def create_subscription(
    req: SubscribeRequest,
    request: Request,
    auth_user: dict = Depends(require_customer),
):
    """Starts a subscription and returns PayPal's approval URL.

    Requires authenticated customer so the account identity (custom_id) can
    be linked to the subscription, preventing unlinked or orphaned payments.
    """
    plan = next(
        (p for p in PLAN_CATALOGUE.get("plans", [])
         if p["id"] == req.plan and p.get("is_active", True)),
        None,
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown plan.")

    if not paypal_provider.client_id:
        raise HTTPException(
            status_code=503, detail="Payments are not configured on this server."
        )

    user_id = auth_user.get("user_id")
    customer_email = auth_user.get("sub")
    if not user_id and customer_email:
        u = repo.get_user_by_email(customer_email)
        if u:
            user_id = u.get("id")

    # Built from the request so the customer returns to the host they started
    # on, rather than a hardcoded domain.
    base = str(request.base_url).rstrip("/")
    result = paypal_provider.create_subscription(
        plan_id=plan["paypal_plan_id"],
        return_url=f"{base}/?subscribed=1",
        cancel_url=f"{base}/?subscribe_cancelled=1",
        subscriber_email=req.email or customer_email,
        custom_id=str(user_id) if user_id else None,
    )

    if not result or not result.approval_url:
        logger.error("PayPal did not return an approval URL for plan %s.", plan["id"])
        raise HTTPException(
            status_code=502, detail="Could not start the subscription. Please try again."
        )

    logger.info("Subscription %s started for plan %s (custom_id: %s)", result.id, plan["id"], user_id)
    return {
        "subscription_id": result.id,
        "status": result.status,
        "approval_url": result.approval_url,
        "plan": plan["id"],
    }


@app.post("/api/webhooks/paypal")
async def paypal_webhook(request: Request):
    """
    Receives and processes PayPal subscription webhook events:
    - BILLING.SUBSCRIPTION.ACTIVATED
    - PAYMENT.SALE.COMPLETED
    - BILLING.SUBSCRIPTION.CANCELLED
    """
    body = await request.body()
    headers = dict(request.headers)

    # Parsed only so a rejected delivery can still be logged. Nothing is acted
    # on until the signature has been verified below.
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        payload = {}

    verified = paypal_provider.verify_webhook(headers, body)
    if not verified:
        logger.warning("PayPal webhook verification failed signature check.")
        repo.record_webhook_event(
            event_type=payload.get("event_type", "unknown"),
            payload=payload,
            result="rejected",
            event_id=payload.get("id"),
            error_detail="Signature verification failed. PayPal will retry delivery.",
        )
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_data = paypal_provider.process_webhook_event(payload)
    
    sub_id = event_data.get("subscription_id")
    event_type = event_data.get("event_type")
    status_str = event_data.get("status")
    email = event_data.get("email")
    custom_id = event_data.get("custom_id")

    # Resolve subscriber identity by custom_id FIRST, then fall back to payer email
    resolved_user = None
    resolved_user_id = None
    resolved_email = email

    if custom_id:
        resolved_user = repo.get_user_by_id(custom_id)
        if not resolved_user:
            resolved_user = repo.get_user_by_email(custom_id)
        if resolved_user:
            resolved_user_id = str(resolved_user.get("id"))
            resolved_email = resolved_user.get("email") or email
            logger.info("Resolved subscription %s to user_id %s via custom_id", sub_id, resolved_user_id)

    if not resolved_user and email:
        resolved_user = repo.get_user_by_email(email)
        if resolved_user:
            resolved_user_id = str(resolved_user.get("id"))
            logger.info("Resolved subscription %s to user_id %s via payer email fallback", sub_id, resolved_user_id)

    if sub_id:
        existing_sub = repo.get_subscription_by_external_id(sub_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        if event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
            access_until = None
            if existing_sub:
                access_until = existing_sub.get("access_until") or existing_sub.get("next_billing_at")
            if not access_until:
                access_until = event_data.get("next_billing_at") or (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

            if existing_sub:
                repo.set_subscription_paused(sub_id, paused_at=now_iso, access_until=access_until)
            else:
                repo.record_subscription(
                    external_sub_id=sub_id,
                    plan_id=event_data.get("plan_id") or payload.get("resource", {}).get("plan_id"),
                    status="paused",
                    user_email=resolved_email,
                    subscriber_name=event_data.get("subscriber_name"),
                    next_billing_at=event_data.get("next_billing_at"),
                    user_id=resolved_user_id,
                )
                repo.set_subscription_paused(sub_id, paused_at=now_iso, access_until=access_until)
            logger.info("Updated subscription %s to paused via BILLING.SUBSCRIPTION.SUSPENDED webhook", sub_id)

        elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
            access_until = None
            if existing_sub:
                access_until = existing_sub.get("access_until") or existing_sub.get("next_billing_at")
            if not access_until:
                access_until = now_iso

            if existing_sub:
                repo.set_subscription_cancelled(sub_id, cancelled_at=now_iso, access_until=access_until, reason="Cancelled via PayPal webhook")
            else:
                repo.record_subscription(
                    external_sub_id=sub_id,
                    plan_id=event_data.get("plan_id") or payload.get("resource", {}).get("plan_id"),
                    status="cancelled",
                    user_email=resolved_email,
                    subscriber_name=event_data.get("subscriber_name"),
                    next_billing_at=None,
                    user_id=resolved_user_id,
                )
                repo.set_subscription_cancelled(sub_id, cancelled_at=now_iso, access_until=access_until, reason="Cancelled via PayPal webhook")
            logger.info("Updated subscription %s to cancelled via BILLING.SUBSCRIPTION.CANCELLED webhook", sub_id)

        elif event_type == "BILLING.SUBSCRIPTION.ACTIVATED" and existing_sub and str(existing_sub.get("status", "")).lower() in ("paused", "suspended"):
            # Resumed subscription: do NOT treat as new signup, do NOT re-grant or reset trial!
            repo.set_subscription_resumed(sub_id, resumed_at=now_iso)
            if event_data.get("next_billing_at"):
                repo.record_subscription(
                    external_sub_id=sub_id,
                    plan_id=existing_sub.get("plan_id") or event_data.get("plan_id"),
                    status="active",
                    user_email=resolved_email or existing_sub.get("user_email"),
                    subscriber_name=event_data.get("subscriber_name") or existing_sub.get("subscriber_name"),
                    next_billing_at=event_data.get("next_billing_at"),
                    user_id=resolved_user_id or existing_sub.get("user_id"),
                )
            logger.info("Resumed subscription %s via BILLING.SUBSCRIPTION.ACTIVATED webhook (was %s)", sub_id, existing_sub.get("status"))

        else:
            next_billing = event_data.get("next_billing_at")
            if not next_billing and status_str in ("active", "completed"):
                plan_str = str(event_data.get("plan_id") or payload.get("resource", {}).get("plan_id") or "").lower()
                days = 365 if ("annual" in plan_str or "4ks" in plan_str) else 30
                next_billing = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

            repo.record_subscription(
                external_sub_id=sub_id,
                plan_id=event_data.get("plan_id") or payload.get("resource", {}).get("plan_id"),
                status=status_str,
                user_email=resolved_email,
                subscriber_name=event_data.get("subscriber_name"),
                next_billing_at=next_billing,
                user_id=resolved_user_id,
            )
            logger.info(f"Updated subscription {sub_id} to status '{status_str}' for user {resolved_user_id or resolved_email} via webhook ({event_type})")

    resource = payload.get("resource", {}) or {}
    amount_block = resource.get("amount") or {}
    try:
        amount = float(amount_block.get("total") or amount_block.get("value"))
    except (TypeError, ValueError):
        amount = None

    repo.record_webhook_event(
        event_type=event_type or "unknown",
        payload=payload,
        result="processed",
        event_id=payload.get("id"),
        subscription_id=sub_id,
        subscriber_name=event_data.get("subscriber_name"),
        amount=amount,
        currency=amount_block.get("currency") or amount_block.get("currency_code"),
    )

    return {"status": "success", "processed": event_data}


# ==========================================
# CUSTOMER AUTHENTICATION ROUTES
# ==========================================

@app.post("/api/auth/register")
async def customer_register(req: CustomerRegisterRequest):
    """Customer registration issuing 14-day free trial and JWT token."""
    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required.",
        )
    if email == ADMIN_EMAIL.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is reserved.",
        )

    password = req.password or ""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 72 bytes or fewer.",
        )

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    existing = repo.get_user_by_email(email)
    if existing:
        if existing.get("is_verified", 0) == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please log in.",
            )
        # Account exists but unverified: update code and resend
        repo.set_verification_code(email, code, expires_at)
        user = existing
    else:
        pwd_hash = get_password_hash(password)
        user = repo.create_user(
            email=email,
            password_hash=pwd_hash,
            full_name=(req.full_name or "").strip() or None,
            trial_days=14,
            is_verified=0,
            verification_code=code,
            verification_code_expires_at=expires_at,
        )

    # Dispatch confirmation email via Resend
    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; max-width:520px; margin:0 auto; padding:24px; border:1px solid #e2e8f0; border-radius:8px; background:#ffffff;">
      <h2 style="color:#0f172a; margin-top:0; font-size:20px;">Confirm your JurisMon email</h2>
      <p style="color:#334155; font-size:14px; line-height:1.6;">Thank you for registering. Please enter the 6-digit confirmation code below to activate your account and start your 14-day free trial:</p>
      <div style="font-size:32px; font-weight:700; letter-spacing:8px; color:#154DA8; background:#f8fafc; border:1px solid #cbd5e1; padding:16px; text-align:center; border-radius:8px; margin:24px 0; font-family:monospace;">
        {code}
      </div>
      <p style="color:#64748b; font-size:12.5px; line-height:1.5;">This code will expire in 15 minutes. If you did not sign up for JurisMon, please disregard this email.</p>
    </div>
    """
    mailer.send(
        subject="Your JurisMon Confirmation Code",
        html=html_body,
        to=[email],
        text=f"Your JurisMon confirmation code is: {code} (expires in 15 minutes).",
    )
    logger.info("Verification code dispatched for %s", email)

    return {
        "status": "verification_required",
        "email": email,
        "message": "A 6-digit confirmation code has been sent to your email. Please confirm your email to activate your account.",
    }


@app.post("/api/auth/verify-code")
async def customer_verify_code(req: VerifyCodeRequest):
    """Verifies confirmation code, activates 14-day free trial, and issues JWT access token."""
    email = (req.email or "").strip().lower()
    code = (req.code or "").strip()
    if not email or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and confirmation code are required.",
        )

    result = repo.verify_user_email(email, code, trial_days=14)
    if not result.get("success"):
        err = result.get("error")
        if err == "code_expired":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation code has expired. Please request a new one.",
            )
        elif err == "user_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid confirmation code. Please check your email and try again.",
            )

    user = result.get("user")
    token = create_customer_token(user_id=user["id"], email=user["email"])
    access = repo.get_user_access_status(user["id"])

    return {
        "status": "verified",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "trial_ends_at": user.get("trial_ends_at"),
            "access": access,
        },
    }


@app.post("/api/auth/resend-code")
async def customer_resend_code(req: ResendCodeRequest):
    """Resends a new 6-digit email confirmation code."""
    email = (req.email or "").strip().lower()
    if email == ADMIN_EMAIL.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is reserved.",
        )
    user = repo.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )

    if user.get("is_verified", 0) == 1:
        return {"status": "already_verified", "message": "Email is already verified. Please log in."}

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    repo.set_verification_code(email, code, expires_at)

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; max-width:520px; margin:0 auto; padding:24px; border:1px solid #e2e8f0; border-radius:8px; background:#ffffff;">
      <h2 style="color:#0f172a; margin-top:0; font-size:20px;">Your new JurisMon confirmation code</h2>
      <p style="color:#334155; font-size:14px; line-height:1.6;">Please enter the confirmation code below to activate your account:</p>
      <div style="font-size:32px; font-weight:700; letter-spacing:8px; color:#154DA8; background:#f8fafc; border:1px solid #cbd5e1; padding:16px; text-align:center; border-radius:8px; margin:24px 0; font-family:monospace;">
        {code}
      </div>
      <p style="color:#64748b; font-size:12.5px; line-height:1.5;">This code will expire in 15 minutes.</p>
    </div>
    """
    mailer.send(
        subject="Your JurisMon Confirmation Code",
        html=html_body,
        to=[email],
        text=f"Your JurisMon confirmation code is: {code} (expires in 15 minutes).",
    )

    return {
        "status": "code_resent",
        "message": "A new confirmation code has been sent to your email.",
    }


_forgot_password_timestamps: Dict[str, List[float]] = {}


@app.post("/api/auth/forgot-password")
async def customer_forgot_password(req: ForgotPasswordRequest):
    """Initiates password reset by issuing a 6-digit verification code.

    Always returns 200 with identical message regardless of whether the email exists.
    Rejects ADMIN_EMAIL with 400.
    Enforces rate limit of 4 requests per email per hour (429).
    """
    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required.",
        )
    if email == ADMIN_EMAIL.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is reserved.",
        )

    # In-memory sliding window rate limit: max 4 requests per email per hour
    now_ts = time.time()
    cutoff = now_ts - 3600
    timestamps = [t for t in _forgot_password_timestamps.get(email, []) if t > cutoff]
    if len(timestamps) >= 4:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please try again later.",
        )
    timestamps.append(now_ts)
    _forgot_password_timestamps[email] = timestamps

    user = repo.get_user_by_email(email)
    if user:
        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        repo.set_verification_code(email, code, expires_at)

        html_body = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; max-width:520px; margin:0 auto; padding:24px; border:1px solid #e2e8f0; border-radius:8px; background:#ffffff;">
          <h2 style="color:#0f172a; margin-top:0; font-size:20px;">Reset your JurisMon password</h2>
          <p style="color:#334155; font-size:14px; line-height:1.6;">We received a request to reset your password. Please enter the 6-digit verification code below to set a new password:</p>
          <div style="font-size:32px; font-weight:700; letter-spacing:8px; color:#154DA8; background:#f8fafc; border:1px solid #cbd5e1; padding:16px; text-align:center; border-radius:8px; margin:24px 0; font-family:monospace;">
            {code}
          </div>
          <p style="color:#64748b; font-size:12.5px; line-height:1.5;">This code will expire in 15 minutes. If you did not request a password reset, you can safely ignore this email.</p>
        </div>
        """
        mailer.send(
            subject="Reset your JurisMon password",
            html=html_body,
            to=[email],
            text=f"Your JurisMon password reset code is: {code} (expires in 15 minutes). If you did not request this, please ignore.",
        )
        logger.info("Password reset code dispatched for %s", email)

    return {
        "status": "success",
        "message": "If an account exists with this email, a password reset code has been sent.",
    }


@app.post("/api/auth/reset-password")
async def customer_reset_password(req: ResetPasswordRequest):
    """Resets user password after verifying 6-digit code."""
    email = (req.email or "").strip().lower()
    code = (req.code or "").strip()
    new_password = req.new_password or ""

    if not email or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and reset code are required.",
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if len(new_password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 72 bytes or fewer.",
        )

    val = repo.validate_verification_code(email, code)
    if not val.get("valid"):
        err = val.get("error")
        if err == "code_expired":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired. Please request a new one.",
            )
        elif err == "user_not_found":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid confirmation code. Please check your email and try again.",
            )

    user = val.get("user") or repo.get_user_by_email(email)
    was_verified = bool(user and user.get("is_verified", 0) == 1)

    pwd_hash = get_password_hash(new_password)
    updated = repo.update_user_password(email, pwd_hash)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password. Please try again.",
        )

    # If the user was not yet verified, activate their trial now using the exact same activation path
    if not was_verified:
        repo.activate_user_trial(email, trial_days=14)
        logger.info("Unverified user %s verified and 14-day trial activated via password reset", email)

    logger.info("Password successfully reset for %s", email)
    return {
        "status": "success",
        "message": "Password updated successfully. Please log in with your new password.",
    }


@app.post("/api/auth/login")
async def customer_login(req: CustomerLoginRequest):
    """Customer login validating credentials and verifying confirmation status."""
    email = (req.email or "").strip().lower()
    if email == ADMIN_EMAIL.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is reserved.",
        )

    user = repo.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    stored_hash = user.get("password_hash", "")
    if not verify_password(req.password or "", stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.get("is_verified", 0) != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not confirmed. Please enter the confirmation code sent to your email.",
        )

    token = create_customer_token(user_id=user["id"], email=user["email"])
    access = repo.get_user_access_status(user["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "trial_ends_at": user.get("trial_ends_at"),
            "access": access,
        },
    }


@app.get("/api/auth/me")
async def get_current_customer_profile(
    auth_user: dict = Depends(require_customer),
):
    """Returns current customer profile, trial status, and subscription state."""
    if is_admin_token(auth_user):
        return {
            "email": auth_user.get("sub", ""),
            "role": "admin",
            "access": {"has_access": True, "reason": "admin"},
        }

    email = auth_user.get("sub", "")
    user = repo.get_user_by_email(email)
    if not user:
        user = repo.get_user_by_id(auth_user.get("user_id", ""))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    access = repo.get_user_access_status(user["id"])
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "trial_started_at": user.get("trial_started_at"),
        "trial_ends_at": user.get("trial_ends_at"),
        "access": access,
    }


# ==========================================
# CUSTOMER SUBSCRIPTION LIFECYCLE ROUTES
# ==========================================

class CustomerCancelRequest(BaseModel):
    reason: Optional[str] = "Customer requested cancellation"


@app.get("/api/account/subscription")
async def get_account_subscription(auth_user: dict = Depends(require_customer)):
    """Returns current subscription details and access status for authenticated customer."""
    user_email = (auth_user.get("sub") or "").strip().lower()
    user_id = auth_user.get("user_id")

    sub = repo.get_subscription_by_email(user_email)
    access_status = repo.get_user_access_status(user_id or user_email)

    if not sub:
        return {
            "has_subscription": False,
            "status": "none",
            "plan": None,
            "plan_id": None,
            "next_billing_at": None,
            "access_until": None,
            "paused_at": None,
            "resumed_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "external_subscription_id": None,
            "access": access_status,
        }

    return {
        "has_subscription": True,
        "status": sub.get("status"),
        "plan": sub.get("plan_id"),
        "plan_id": sub.get("plan_id"),
        "next_billing_at": sub.get("next_billing_at"),
        "access_until": sub.get("access_until"),
        "paused_at": sub.get("paused_at"),
        "resumed_at": sub.get("resumed_at"),
        "cancelled_at": sub.get("cancelled_at"),
        "cancel_reason": sub.get("cancel_reason"),
        "external_subscription_id": sub.get("external_subscription_id"),
        "access": access_status,
    }


@app.post("/api/account/subscription/pause")
async def pause_customer_subscription(auth_user: dict = Depends(require_customer)):
    """Pauses (suspends) subscription billing with access retained through the paid period."""
    user_email = (auth_user.get("sub") or "").strip().lower()
    sub = repo.get_subscription_by_email(user_email)
    if not sub or not sub.get("external_subscription_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found to pause.",
        )

    ext_id = sub["external_subscription_id"]
    sub_lock = _subscription_locks[ext_id]
    async with sub_lock:
        fresh_sub = repo.get_subscription_by_external_id(ext_id) or sub
        current_status = str(fresh_sub.get("status") or "").lower()

        if current_status in ("paused", "suspended"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription is already paused.",
            )
        if current_status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot pause a cancelled subscription.",
            )
        if current_status not in ("active", "completed"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot pause subscription with status '{current_status}'.",
            )

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        access_until = fresh_sub.get("next_billing_at")
        if not access_until:
            access_until = (now + timedelta(days=30)).isoformat()

        # Call PayPal FIRST
        success = paypal_provider.suspend_subscription(
            ext_id, reason="Customer requested pause via self-service portal"
        )
        if not success:
            logger.error("PayPal failed to suspend subscription %s for %s", ext_id, user_email)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal did not accept the pause request. Please try again or contact support.",
            )

        # Mutate local database state only upon PayPal success
        repo.set_subscription_paused(ext_id, paused_at=now_iso, access_until=access_until)
        repo.record_webhook_event(
            event_type="CUSTOMER.SUBSCRIPTION.PAUSED",
            payload={
                "subscription_id": ext_id,
                "action": "pause",
                "user_email": user_email,
                "access_until": access_until,
            },
            result="processed",
            subscription_id=ext_id,
        )
        logger.info("Customer %s paused subscription %s (access until %s)", user_email, ext_id, access_until)

        return {
            "status": "paused",
            "subscription_id": ext_id,
            "paused_at": now_iso,
            "access_until": access_until,
            "message": f"Billing paused. Your access continues until {access_until[:10]}.",
        }


@app.post("/api/account/subscription/resume")
async def resume_customer_subscription(auth_user: dict = Depends(require_customer)):
    """Resumes a paused customer subscription."""
    user_email = (auth_user.get("sub") or "").strip().lower()
    sub = repo.get_subscription_by_email(user_email)
    if not sub or not sub.get("external_subscription_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No paused subscription found to resume.",
        )

    ext_id = sub["external_subscription_id"]
    sub_lock = _subscription_locks[ext_id]
    async with sub_lock:
        fresh_sub = repo.get_subscription_by_external_id(ext_id) or sub
        current_status = str(fresh_sub.get("status") or "").lower()

        if current_status in ("active", "completed"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription is already active.",
            )
        if current_status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot resume a cancelled subscription. Please subscribe to a new plan.",
            )
        if current_status not in ("paused", "suspended"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resume subscription with status '{current_status}'.",
            )

        now_iso = datetime.now(timezone.utc).isoformat()

        # Call PayPal FIRST
        success = paypal_provider.activate_subscription(
            ext_id, reason="Customer requested resume via self-service portal"
        )
        if not success:
            logger.error("PayPal failed to activate subscription %s for %s", ext_id, user_email)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal did not accept the resume request. Please try again or contact support.",
            )

        # Mutate local database state only upon PayPal success
        repo.set_subscription_resumed(ext_id, resumed_at=now_iso)
        repo.record_webhook_event(
            event_type="CUSTOMER.SUBSCRIPTION.RESUMED",
            payload={
                "subscription_id": ext_id,
                "action": "resume",
                "user_email": user_email,
            },
            result="processed",
            subscription_id=ext_id,
        )
        logger.info("Customer %s resumed subscription %s", user_email, ext_id)

        return {
            "status": "active",
            "subscription_id": ext_id,
            "resumed_at": now_iso,
            "message": "Subscription reactivated successfully.",
        }


@app.post("/api/account/subscription/cancel")
async def cancel_customer_subscription(
    req: CustomerCancelRequest = CustomerCancelRequest(),
    auth_user: dict = Depends(require_customer),
):
    """Cancels customer subscription with access retained through the paid period."""
    user_email = (auth_user.get("sub") or "").strip().lower()
    sub = repo.get_subscription_by_email(user_email)
    if not sub or not sub.get("external_subscription_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found to cancel.",
        )

    ext_id = sub["external_subscription_id"]
    sub_lock = _subscription_locks[ext_id]
    async with sub_lock:
        fresh_sub = repo.get_subscription_by_external_id(ext_id) or sub
        current_status = str(fresh_sub.get("status") or "").lower()

        if current_status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription is already cancelled.",
            )

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        access_until = fresh_sub.get("access_until") or fresh_sub.get("next_billing_at")
        if not access_until:
            access_until = now_iso

        cancel_reason = (req.reason or "Customer requested cancellation").strip()

        # Call PayPal FIRST
        success = paypal_provider.cancel_subscription(ext_id, reason=cancel_reason)
        if not success:
            logger.error("PayPal failed to cancel subscription %s for %s", ext_id, user_email)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal did not accept the cancellation. The subscription is still active.",
            )

        # Mutate local database state only upon PayPal success
        repo.set_subscription_cancelled(
            ext_id, cancelled_at=now_iso, access_until=access_until, reason=cancel_reason
        )
        repo.record_webhook_event(
            event_type="CUSTOMER.SUBSCRIPTION.CANCELLED",
            payload={
                "subscription_id": ext_id,
                "action": "cancel",
                "user_email": user_email,
                "access_until": access_until,
                "reason": cancel_reason,
            },
            result="processed",
            subscription_id=ext_id,
        )
        logger.info("Customer %s cancelled subscription %s (access retained until %s)", user_email, ext_id, access_until)

        return {
            "status": "cancelled",
            "subscription_id": ext_id,
            "cancelled_at": now_iso,
            "access_until": access_until,
            "message": f"Subscription cancelled. Your access continues until {access_until[:10]}.",
        }


# ==========================================
# ADMIN AUTH & MANAGEMENT ROUTES
# ==========================================

@app.post("/api/admin/login")
async def admin_login(req: LoginRequest):
    """Admin login returning JWT bearer token."""
    if not authenticate_admin(req.email, req.password):
        logger.warning("Failed admin login attempt for '%s'.", req.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials"
        )
    token = create_access_token({"sub": ADMIN_EMAIL})
    return {"access_token": token, "token_type": "bearer"}


def _run_background_crawl(run_id: str):
    try:
        from scripts.run_crawler import main as execute_crawl
        execute_crawl(run_id=run_id)
    except Exception as e:
        logger.error(f"Background crawl execution error for {run_id}: {e}")


@app.post("/api/admin/crawl/run")
async def trigger_admin_crawl(
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_admin),
):
    """Trigger background crawler execution. Refuses with 409 if a crawl is already running."""
    active_run = repo.get_active_crawl_run()
    if active_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crawl is already running.",
        )

    run_id = repo.start_crawl_run()

    # In production on Linux with systemctl, trigger jurismon-crawl.service out-of-process
    is_systemd = (
        sys.platform.startswith("linux")
        and shutil.which("systemctl") is not None
        and os.path.exists("/etc/systemd")
    )
    if is_systemd:
        try:
            subprocess.Popen(
                ["sudo", "systemctl", "start", "jurismon-crawl.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {
                "status": "started",
                "crawl_run_id": run_id,
                "message": "Crawl run triggered via jurismon-crawl.service.",
            }
        except Exception as e:
            logger.error(f"Failed to start jurismon-crawl.service via systemctl: {e}")
            background_tasks.add_task(_run_background_crawl, run_id)
            return {
                "status": "started",
                "crawl_run_id": run_id,
                "message": "Crawl run kicked off in background (systemctl fallback).",
            }

    background_tasks.add_task(_run_background_crawl, run_id)

    return {
        "status": "started",
        "crawl_run_id": run_id,
        "message": "Crawl run kicked off in background.",
    }


@app.get("/api/admin/crawl/status")
async def get_admin_crawl_status(
    admin: dict = Depends(require_admin),
):
    """Returns the latest crawl run status, timestamps, counts, and errors."""
    latest = repo.get_latest_crawl_run()
    if not latest:
        return {
            "status": "none",
            "message": "No crawl runs recorded.",
        }
    crawled = latest.get("total_sources") or 0
    failed = latest.get("sources_failed") or 0
    succeeded = latest.get("sources_succeeded") if latest.get("sources_succeeded") is not None else max(0, crawled - failed)
    skipped = latest.get("sources_skipped") if latest.get("sources_skipped") is not None else max(0, 65 - crawled)
    latest["sources_skipped"] = skipped
    latest["summary"] = f"{crawled} crawled, {succeeded} succeeded, {failed} failed, {skipped} skipped"
    return latest


@app.get("/api/admin/overview")
async def admin_overview(admin: dict = Depends(require_admin)):
    """Admin dashboard stats overview with detailed health breakdown."""
    all_sources = repo.get_all_sources()
    # health_status is authoritative; falling back to is_active counted every
    # parked source as operational.
    operational = [s for s in all_sources if s.get("health_status") == "operational"]
    cloudflare = [s for s in all_sources if s.get("health_status") == "cloudflare_blocked"]
    dead = [s for s in all_sources if s.get("health_status") == "dead_link"]
    subs = repo.list_subscriptions()

    by_paypal_id = {p["paypal_plan_id"]: p for p in PLAN_CATALOGUE.get("plans", [])}
    active = [s for s in subs if s.get("status") == "active"]

    # Annual plans are divided by twelve so monthly and annual subscribers can
    # be summed into one comparable figure.
    mrr = sum(
        _monthly_value(by_paypal_id[s["plan_id"]])
        for s in active
        if s.get("plan_id") in by_paypal_id
    )

    return {
        "status": "healthy",
        "total_configured": len(all_sources),
        "total_monitored_sources": len(operational),
        "operational_sources": len(operational),
        "cloudflare_blocked": len(cloudflare),
        "dead_links": len(dead),
        "total_subscribers": len(subs),
        "active_subscribers": len(active),
        "past_due_subscribers": sum(1 for s in subs if s.get("status") in ("past_due", "suspended", "paused")),
        "cancelled_subscribers": sum(1 for s in subs if s.get("status") in ("cancelled", "expired")),
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "currency": PLAN_CATALOGUE.get("currency", "USD"),
        "payment_mode": paypal_provider.mode,
        "paypal_configured": bool(paypal_provider.client_id),
    }


@app.get("/api/admin/subscribers")
async def list_subscribers(admin: dict = Depends(require_admin)):
    """Returns subscribers with their plan resolved, for the admin dashboard."""
    by_paypal_id = {p["paypal_plan_id"]: p for p in PLAN_CATALOGUE.get("plans", [])}

    subscribers = []
    for row in repo.list_subscriptions():
        plan = by_paypal_id.get(row.get("plan_id"))
        subscribers.append({
            "id": row.get("id"),
            "name": row.get("subscriber_name") or row.get("user_email") or "Unknown subscriber",
            "email": row.get("user_email"),
            "status": row.get("status"),
            "paypal": row.get("external_subscription_id"),
            "next_billing_at": row.get("next_billing_at"),
            "created_at": row.get("created_at"),
            # plan_id is null when a webhook for an unknown plan arrives, so the
            # dashboard must render the row rather than drop the subscriber.
            "plan": plan["id"] if plan else None,
            "plan_name": plan["name"] if plan else "Unrecognised plan",
            "plan_price": plan["price"] if plan else None,
            "plan_interval": plan["interval"] if plan else None,
        })

    return {"count": len(subscribers), "subscribers": subscribers}


@app.get("/api/admin/plans")
async def list_plans(admin: dict = Depends(require_admin)):
    """Returns the plan catalogue with live subscriber counts."""
    subs = repo.list_subscriptions()

    plans = []
    for plan in PLAN_CATALOGUE.get("plans", []):
        active = sum(
            1 for s in subs
            if s.get("plan_id") == plan["paypal_plan_id"] and s.get("status") == "active"
        )
        plans.append({
            "id": plan["id"],
            "name": plan["name"],
            "price": plan["price"],
            "interval": plan["interval"],
            "paypal": plan["paypal_plan_id"],
            "is_active": plan.get("is_active", True),
            "subscribers": active,
        })

    return {
        "currency": PLAN_CATALOGUE.get("currency", "USD"),
        "trial_days": PLAN_CATALOGUE.get("trial_days", 0),
        "count": len(plans),
        "plans": plans,
    }


@app.post("/api/admin/subscriptions/{external_id}/cancel")
async def cancel_subscription(external_id: str, admin: dict = Depends(require_admin)):
    """Cancels a subscription at PayPal, then records it locally.

    PayPal is the source of truth for billing, so the local status is only
    updated once PayPal confirms. Marking it cancelled here without telling
    PayPal would leave the customer being charged.
    """
    if not paypal_provider.client_id:
        raise HTTPException(
            status_code=503, detail="PayPal is not configured on this server."
        )

    cancelled = paypal_provider.cancel_subscription(external_id, reason="Cancelled by administrator")
    if not cancelled:
        logger.error(f"PayPal refused to cancel subscription {external_id}")
        raise HTTPException(
            status_code=502,
            detail="PayPal did not accept the cancellation. The subscription is still active.",
        )

    repo.record_subscription(
        external_sub_id=external_id,
        plan_id=None,
        status="cancelled",
    )
    logger.info(f"Subscription {external_id} cancelled by admin")

    return {"status": "cancelled", "subscription_id": external_id}


@app.get("/api/admin/webhooks")
async def list_webhook_events(
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    """Returns recent PayPal deliveries with their payloads, for debugging."""
    events = []
    for row in repo.list_webhook_events(limit=limit):
        try:
            payload = json.loads(row.get("payload") or "{}")
        except ValueError:
            payload = {}

        events.append({
            "id": row.get("id"),
            "event_id": row.get("event_id"),
            "type": row.get("event_type"),
            "sub": row.get("subscriber_name") or row.get("subscription_id") or "Unknown",
            "amount": row.get("amount"),
            "currency": row.get("currency"),
            "result": row.get("result"),
            "error": row.get("error_detail"),
            "received_at": row.get("received_at"),
            "payload": payload,
        })

    return {
        "count": len(events),
        "failed": sum(1 for e in events if e["result"] != "processed"),
        "events": events,
    }
