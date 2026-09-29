"""JurisMon Production FastAPI Backend.

Sub-Task 4.4:
Provides:
- Instant Full-Text Search API across snapshots & statutory diff deltas
- PayPal Subscriptions & Webhook Processing Engine
- Secure Admin Authentication & Subscriber Management
- Serves Minimalist Search UI & Admin Dashboard
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException, Query, Depends, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.repository import Repository
from api.auth import create_access_token, require_admin, authenticate_admin, ADMIN_EMAIL
from api.payments.paypal_provider import PayPalProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jurismon.api")

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
async def search_endpoint(q: str = Query(default="", description="Search keyword or section number")):
    """Instant search querying statutory text snapshots and calculated diffs."""
    results = repo.search_snapshots_and_diffs(query=q)
    items = format_result_items(results)
    return {
        "query": q,
        "total_snapshots": len(results.get("snapshots", [])),
        "total_diffs": len(results.get("diffs", [])),
        "results": results,
        "items": items,
    }


@app.get("/api/sources")
async def list_sources(filter_type: Optional[str] = Query(default="all")):
    """Lists municipal sources with real-world audit categorization."""
    all_sources = repo.get_all_sources()
    # health_status is authoritative; falling back to is_active counted every
    # parked source as operational.
    operational = [s for s in all_sources if s.get("health_status") == "operational"]
    cloudflare = [s for s in all_sources if s.get("health_status") == "cloudflare_blocked"]
    dead_links = [s for s in all_sources if s.get("health_status") == "dead_link"]

    return {
        "count": len(all_sources),
        "total_configured": len(all_sources),
        "operational_count": len(operational),
        "cloudflare_count": len(cloudflare),
        "dead_links_count": len(dead_links),
        "sources": all_sources,
    }


# ==========================================
# PAYPAL SUBSCRIPTIONS & WEBHOOK ROUTE
# ==========================================

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

    if sub_id:
        repo.record_subscription(
            external_sub_id=sub_id,
            plan_id=event_data.get("plan_id") or payload.get("resource", {}).get("plan_id"),
            status=status_str,
            user_email=email,
            subscriber_name=event_data.get("subscriber_name"),
            next_billing_at=event_data.get("next_billing_at"),
        )
        logger.info(f"Updated subscription {sub_id} to status '{status_str}' via webhook ({event_type})")

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
        "past_due_subscribers": sum(1 for s in subs if s.get("status") in ("past_due", "suspended")),
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
