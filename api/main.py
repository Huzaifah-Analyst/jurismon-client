"""JurisMon Production FastAPI Backend.

Sub-Task 4.4:
Provides:
- Instant Full-Text Search API across snapshots & statutory diff deltas
- PayPal Subscriptions & Webhook Processing Engine
- Secure Admin Authentication & Subscriber Management
- Serves Minimalist Search UI & Admin Dashboard
"""

import os
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
    operational = [s for s in all_sources if s.get("health_status") == "operational" or s.get("is_active")]
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

    verified = paypal_provider.verify_webhook(headers, body)
    if not verified:
        logger.warning("PayPal webhook verification failed signature check.")
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event_data = paypal_provider.process_webhook_event(payload)
    
    sub_id = event_data.get("subscription_id")
    event_type = event_data.get("event_type")
    status_str = event_data.get("status")
    email = event_data.get("email")

    if sub_id:
        repo.record_subscription(
            external_sub_id=sub_id,
            plan_id=payload.get("resource", {}).get("plan_id", "default_plan"),
            status=status_str,
            user_email=email,
        )
        logger.info(f"Updated subscription {sub_id} to status '{status_str}' via webhook ({event_type})")

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
    operational = [s for s in all_sources if s.get("health_status") == "operational" or s.get("is_active")]
    cloudflare = [s for s in all_sources if s.get("health_status") == "cloudflare_blocked"]
    dead = [s for s in all_sources if s.get("health_status") == "dead_link"]
    subs = repo.list_subscriptions()

    return {
        "status": "healthy",
        "total_configured": len(all_sources),
        "total_monitored_sources": len(operational),
        "operational_sources": len(operational),
        "cloudflare_blocked": len(cloudflare),
        "dead_links": len(dead),
        "total_subscribers": len(subs),
        "payment_mode": paypal_provider.mode,
        "paypal_configured": bool(paypal_provider.client_id),
    }


@app.get("/api/admin/subscribers")
async def list_subscribers(admin: dict = Depends(require_admin)):
    """Returns full subscribers list for client management."""
    subs = repo.list_subscriptions()
    return {"count": len(subs), "subscribers": subs}
