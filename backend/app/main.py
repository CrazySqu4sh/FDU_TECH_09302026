"""Aparece API. Run: uvicorn app.main:app --reload  (from the backend folder)"""
import json
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agents, services
from .db import get_db, init_db, log, now, row, rows
from .seed import seed

EVIDENCE = {"system", "document", "owner"}
CATEGORIES = {"hours", "price", "service", "language", "contact", "policy", "stock", "shipping", "returns"}
SEGMENTS = {"ecommerce", "services"}


@asynccontextmanager
async def lifespan(app):
    init_db()
    with get_db() as db:
        for bid in seed(db):
            if agents.is_demo():
                services.run_scan(db, bid)  # first scan so the demo opens with data
    yield


app = FastAPI(title="Aparece API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class FactIn(BaseModel):
    key: str | None = None
    product: str = ""
    product_es: str = ""
    label: str
    label_es: str = ""
    value: str
    category: str
    evidence: str = "owner"
    source: str = "Owner entry"


class BusinessIn(BaseModel):
    name: str
    category: str
    category_es: str = ""
    segment: str = "services"
    city: str
    website: str = ""
    competitors: list[str] = Field(default_factory=list)
    facts: list[FactIn] = Field(default_factory=list)


class FactsConfirm(BaseModel):
    facts: list[FactIn]
    confirmed_by: str


class Approval(BaseModel):
    approver: str
    note: str = ""


def _key(f: FactIn) -> str:
    if f.key:
        return f.key
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")  # noqa: E731
    if f.product:
        return f"product.{slug(f.product)}.{f.category}"
    return f"{f.category}.{slug(f.label)}"


def _check_fact(f: FactIn):
    if f.category not in CATEGORIES:
        raise HTTPException(422, f"Category must be one of {sorted(CATEGORIES)}")
    if f.evidence not in EVIDENCE:
        raise HTTPException(422, f"Evidence must be one of {sorted(EVIDENCE)}")


def _upsert_facts(db, bid: int, facts: list[FactIn], actor: str):
    for f in facts:
        _check_fact(f)
        db.execute(
            "INSERT INTO facts (business_id, key, product, product_es, label, label_es, value, category, evidence, "
            "source, verified_by, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(business_id, key) DO UPDATE "
            "SET product=excluded.product, product_es=excluded.product_es, "
            "label=excluded.label, label_es=excluded.label_es, value=excluded.value, category=excluded.category, "
            "evidence=excluded.evidence, source=excluded.source, verified_by=excluded.verified_by, "
            "verified_at=excluded.verified_at",
            (bid, _key(f), f.product, f.product_es, f.label, f.label_es, f.value, f.category, f.evidence, f.source,
             actor, now()))
    log(db, bid, "facts_confirmed", actor, {"count": len(facts)})


def _biz_or_404(db, bid):
    biz = services.load_business(db, bid)
    if not biz:
        raise HTTPException(404, "Business not found")
    return biz


@app.get("/api/status")
def status():
    return {"mode": "demo" if agents.is_demo() else "live", "providers": agents.providers()}


@app.get("/api/businesses")
def list_businesses():
    with get_db() as db:
        return rows(db.execute("SELECT id, name, category, segment, city FROM businesses ORDER BY id"))


@app.post("/api/businesses", status_code=201)
def create_business(body: BusinessIn):
    if body.segment not in SEGMENTS:
        raise HTTPException(422, "Segment must be 'ecommerce' or 'services'")
    with get_db() as db:
        bid = db.execute(
            "INSERT INTO businesses (name, category, category_es, segment, city, website, competitors, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (body.name, body.category, body.category_es, body.segment, body.city, body.website,
             json.dumps(body.competitors), now())).lastrowid
        log(db, bid, "business_created", body.name)
        if body.facts:
            _upsert_facts(db, bid, body.facts, "Owner (onboarding)")
        return {"id": bid}


@app.get("/api/businesses/{bid}/dashboard")
def get_dashboard(bid: int):
    with get_db() as db:
        _biz_or_404(db, bid)
        return services.dashboard(db, bid)


@app.put("/api/businesses/{bid}/facts")
def confirm_facts(bid: int, body: FactsConfirm):
    """Owner reviews and confirms the verified profile. Only a named person can do this."""
    if not body.confirmed_by.strip():
        raise HTTPException(422, "Enter the name of the person confirming these facts")
    with get_db() as db:
        _biz_or_404(db, bid)
        _upsert_facts(db, bid, body.facts, body.confirmed_by.strip())
        return {"ok": True}


@app.delete("/api/businesses/{bid}/facts/{key}")
def delete_fact(bid: int, key: str):
    with get_db() as db:
        db.execute("DELETE FROM facts WHERE business_id=? AND key=?", (bid, key))
        log(db, bid, "fact_deleted", "owner", {"key": key})
        return {"ok": True}


@app.get("/api/businesses/{bid}/journeys")
def get_journeys(bid: int):
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        return services.ensure_journeys(db, biz, services.load_facts(db, bid))


@app.post("/api/businesses/{bid}/journeys/regenerate")
def regenerate_journeys(bid: int):
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        return services.ensure_journeys(db, biz, services.load_facts(db, bid), regenerate=True)


@app.post("/api/businesses/{bid}/scans")
def scan(bid: int):
    with get_db() as db:
        _biz_or_404(db, bid)
        if not services.load_facts(db, bid):
            raise HTTPException(422, "Add and confirm at least one verified fact before scanning")
        return services.run_scan(db, bid)


@app.get("/api/businesses/{bid}/answers")
def answers(bid: int, scan_id: int | None = None):
    with get_db() as db:
        if scan_id is None:
            s = row(db.execute("SELECT id FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (bid,)))
            if not s:
                return []
            scan_id = s["id"]
        resp = rows(db.execute(
            "SELECT r.*, j.question, j.language, j.category FROM responses r JOIN journeys j ON j.id=r.journey_id "
            "WHERE r.scan_id=? ORDER BY j.id, r.provider", (scan_id,)))
        for r in resp:
            r["competitors"] = json.loads(r["competitors"])
            r["claims"] = rows(db.execute("SELECT fact_key, value, verdict FROM claims WHERE response_id=?",
                                          (r["id"],)))
        return resp


@app.post("/api/incidents/{iid}/draft-fix")
def draft_fix(iid: int):
    """Automatic: the Fix Agent drafts. Nothing is published."""
    with get_db() as db:
        inc = row(db.execute("SELECT * FROM incidents WHERE id=?", (iid,)))
        if not inc:
            raise HTTPException(404, "Issue not found")
        biz = services.load_business(db, inc["business_id"])
        fact = row(db.execute("SELECT * FROM facts WHERE business_id=? AND key=?",
                              (inc["business_id"], inc["fact_key"]))) if inc["fact_key"] else None
        fix = agents.generate_fix(inc, biz, fact)
        db.execute("UPDATE incidents SET suggested_fix=? WHERE id=?", (json.dumps(fix, ensure_ascii=False), iid))
        log(db, inc["business_id"], "fix_drafted", "fix_agent", {"incident_id": iid})
        return fix


@app.post("/api/incidents/{iid}/approve")
def approve(iid: int, body: Approval):
    """Human gate: a named person approves the fix before anything goes public."""
    if not body.approver.strip():
        raise HTTPException(422, "Enter the name of the person approving this fix")
    with get_db() as db:
        inc = row(db.execute("SELECT * FROM incidents WHERE id=?", (iid,)))
        if not inc:
            raise HTTPException(404, "Issue not found")
        if not inc["suggested_fix"]:
            raise HTTPException(409, "Draft a fix before approving")
        if inc["status"] not in ("open", "needs_review"):
            raise HTTPException(409, f"Issue is already {inc['status']}")
        db.execute("UPDATE incidents SET status='approved', approved_by=?, approved_at=? WHERE id=?",
                   (body.approver.strip(), now(), iid))
        log(db, inc["business_id"], "fix_approved", body.approver.strip(), {"incident_id": iid, "note": body.note})
        return {"ok": True}


@app.post("/api/incidents/{iid}/dismiss")
def dismiss(iid: int, body: Approval):
    with get_db() as db:
        inc = row(db.execute("SELECT * FROM incidents WHERE id=?", (iid,)))
        if not inc:
            raise HTTPException(404, "Issue not found")
        db.execute("UPDATE incidents SET status='dismissed' WHERE id=?", (iid,))
        log(db, inc["business_id"], "incident_dismissed", body.approver or "unknown",
            {"incident_id": iid, "note": body.note})
        return {"ok": True}


@app.get("/api/businesses/{bid}/audit")
def audit(bid: int):
    with get_db() as db:
        return rows(db.execute("SELECT * FROM audit_log WHERE business_id=? ORDER BY id DESC LIMIT 100", (bid,)))


# Serve the built React app (frontend/dist) from the same server when it exists,
# so a demo only needs one command: uvicorn app.main:app
import os  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
