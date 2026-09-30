"""Aparece API. Run: uvicorn app.main:app --reload  (from the backend folder)"""
import json
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agents, assistant, evidence, insights, plans, prooflab, sales, services, site_audit
from .db import get_db, init_db, log, now, row, rows
from .seed import seed

EVIDENCE = {"system", "document", "owner"}
CATEGORIES = {"hours", "price", "service", "language", "contact", "policy", "stock", "shipping", "returns",
              "spec", "feature", "warranty", "license", "insurance", "service_area"}
SEGMENTS = {"cleaning", "restaurant", "trades", "ecommerce", "tech", "services"}


@asynccontextmanager
async def lifespan(app):
    init_db()
    with get_db() as db:
        new = seed(db)
        for bid in [r[0] for r in db.execute("SELECT id FROM businesses")]:
            sales.ensure_history(db, services.load_business(db, bid))
        for bid in new:
            if agents.is_demo():
                biz = services.load_business(db, bid)
                evidence.verify_facts(db, bid, services.load_facts(db, bid), biz)  # confirm facts on listings
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


class SalesWeek(BaseModel):
    phase: str = "after"  # "before" or "after" monitoring started
    search_sessions: int
    ai_sessions: int
    ai_orders: int
    ai_revenue: float
    misinfo_contacts: int | None = None


class PlanChange(BaseModel):
    plan: str


class CheckFact(BaseModel):
    label: str
    label_es: str = ""
    value: str
    category: str


class CheckIn(BaseModel):
    name: str
    category: str
    category_es: str = ""
    segment: str = "services"
    city: str
    competitors: list[str] = Field(default_factory=list)
    facts: list[CheckFact] = Field(default_factory=list, max_length=5)


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
        return rows(db.execute("SELECT id, name, category, segment, city, plan FROM businesses ORDER BY id"))


@app.get("/api/plans")
def get_plans():
    return plans.catalog()


@app.put("/api/businesses/{bid}/plan")
def change_plan(bid: int, body: PlanChange):
    """Demo: switches plan directly. Production puts a payment step (e.g. Stripe Checkout) in front."""
    if body.plan not in plans.PLANS:
        raise HTTPException(422, f"Plan must be one of {list(plans.PLANS)}")
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        if biz["plan"] != body.plan:
            db.execute("UPDATE businesses SET plan=?, plan_started_at=? WHERE id=?", (body.plan, now(), bid))
            log(db, bid, "plan_changed", "owner", {"from": biz["plan"], "to": body.plan})
        return {"ok": True}


@app.post("/api/check")
def free_check(body: CheckIn):
    """Free AI Check: no account needed. Saved so it can become a trial in one click."""
    if not (body.name.strip() and body.category.strip() and body.city.strip()):
        raise HTTPException(422, "Fill in name, type, and city")
    if body.segment not in SEGMENTS:
        raise HTTPException(422, f"Segment must be one of {sorted(SEGMENTS)}")
    for f in body.facts:
        if f.category not in CATEGORIES:
            raise HTTPException(422, f"Category must be one of {sorted(CATEGORIES)}")
    req = body.model_dump()
    req["facts"] = [f for f in req["facts"] if f["label"].strip() and f["value"].strip()]
    result = services.run_check(req)
    with get_db() as db:
        cid = db.execute("INSERT INTO checks (name, request, result, created_at) VALUES (?,?,?,?)",
                         (body.name, json.dumps(req), json.dumps(result), now())).lastrowid
    return {"id": cid, **result}


CATEGORY = {"cleaning": ("house cleaning service", "servicio de limpieza de casas"), "restaurant": ("restaurant", "restaurante"), "trades": ("contractor", "contratista"),
            "services": ("local service business", "negocio de servicios"), "ecommerce": ("online store", "tienda en línea"),
            "tech": ("tech store", "tienda de tecnología")}


class QuickScanIn(BaseModel):
    url: str = Field(min_length=4, max_length=300)
    name: str = Field("", max_length=120)
    city: str = Field("", max_length=120)
    segment: str = ""
    lead_id: int | None = None


LEAD_REASONS = {"fewer_calls", "competitors", "wrong_info", "curious", "spanish", "referred", "other"}
LEAD_ISSUES = {"not_found", "wrong_info", "website", "no_time", "reviews", "spanish", "unsure"}
LEAD_STATUS = {"new", "contacted", "trial", "customer", "not_fit"}


class LeadIn(BaseModel):
    contact_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
    phone: str = Field("", max_length=40)
    role: str = Field("", max_length=40)
    business_name: str = Field(min_length=2, max_length=120)
    website: str = Field(min_length=4, max_length=300)
    city: str = Field("", max_length=120)
    segment: str = ""
    reasons: list[str] = Field(default_factory=list, max_length=7)
    issues: list[str] = Field(default_factory=list, max_length=7)
    issue_text: str = Field("", max_length=1000)
    help_text: str = Field("", max_length=1000)
    lang: str = "en"
    consent: bool


@app.post("/api/leads", status_code=201)
def create_lead(body: LeadIn):
    """Sign-up before the free scan: who they are, why they came, what they think is wrong, how we can help."""
    if not body.consent:
        raise HTTPException(422, "Please agree so we can send you your results")
    with get_db() as db:
        lid = db.execute(
            "INSERT INTO leads (created_at, contact_name, email, phone, role, business_name, website, city, segment, "
            "reasons, issues, issue_text, help_text, lang, consent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now(), body.contact_name.strip(), body.email.strip().lower(), body.phone.strip(), body.role,
             body.business_name.strip(), body.website.strip(), body.city.strip(),
             body.segment if body.segment in SEGMENTS else "",
             json.dumps([r for r in body.reasons if r in LEAD_REASONS]), json.dumps([i for i in body.issues if i in LEAD_ISSUES]),
             body.issue_text.strip(), body.help_text.strip(), body.lang if body.lang in ("en", "es") else "en", 1)).lastrowid
        return {"id": lid}


def _lead_rows(db) -> list[dict]:
    out = rows(db.execute("SELECT * FROM leads ORDER BY id DESC"))
    for l in out:
        l["reasons"], l["issues"] = json.loads(l["reasons"]), json.loads(l["issues"])
        l["scan"] = None
        if l["check_id"]:
            c = row(db.execute("SELECT result FROM checks WHERE id=?", (l["check_id"],)))
            if c:
                r = json.loads(c["result"])
                l["scan"] = {"inclusion": r.get("inclusion"), "inclusion_es": r.get("inclusion_es"), "missed": r.get("missed"),
                             "wrong_facts": r.get("wrong_facts"), "answers": r.get("answers"), "mode": r.get("mode"),
                             "site_score": r.get("site_score")}
    return out


@app.get("/api/leads")
def list_leads():
    """Internal: everyone who signed up for a free scan, with their answers and results.
    Demo has no login; before launch this sits behind staff sign-in."""
    with get_db() as db:
        return _lead_rows(db)


class LeadUpdate(BaseModel):
    status: str
    note: str = Field("", max_length=1000)


@app.put("/api/leads/{lid}")
def update_lead(lid: int, body: LeadUpdate):
    if body.status not in LEAD_STATUS:
        raise HTTPException(422, f"Status must be one of {sorted(LEAD_STATUS)}")
    with get_db() as db:
        db.execute("UPDATE leads SET status=?, note=? WHERE id=?", (body.status, body.note, lid))
        return {"ok": True}


@app.get("/api/leads.csv", response_class=PlainTextResponse)
def leads_csv():
    import csv
    import io
    with get_db() as db:
        ls = _lead_rows(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "signed_up", "name", "email", "phone", "role", "business", "website", "city", "type", "why_checking",
                "problems", "tell_us_more", "how_we_can_help", "named_%", "named_es_%", "missed_answers", "wrong_facts",
                "website_score", "scan_mode", "status", "note"])
    for l in ls:
        s = l["scan"] or {}
        w.writerow([l["id"], l["created_at"], l["contact_name"], l["email"], l["phone"], l["role"], l["business_name"],
                    l["website"], l["city"], l["segment"], "; ".join(l["reasons"]), "; ".join(l["issues"]), l["issue_text"],
                    l["help_text"], s.get("inclusion", ""), s.get("inclusion_es", ""), s.get("missed", ""),
                    s.get("wrong_facts", ""), s.get("site_score", ""), s.get("mode", ""), l["status"], l["note"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=aparece-leads.csv"})


@app.post("/api/quick-scan")
def quick_scan(body: QuickScanIn):
    """One box, one step: a website address in, a full AI visibility report out. No CSV, no CRM, no account.
    Reads the site (name, city, type, facts, services), asks the assistants customer questions (one per service
    found), and saves it as a free check so 'Start free trial' carries everything over."""
    if not re.match(r"^(https?://)?[a-z0-9.-]+\.[a-z]{2,}(/\S*)?$", body.url.strip(), re.I):
        raise HTTPException(422, "Enter a website address like brillocleaning.com")
    seg = body.segment if body.segment in SEGMENTS else ""
    with get_db() as db:
        site = site_audit.audit(db, body.url, body.name, body.city, seg)
    blocked = not site["ok"]
    if blocked and site["error_kind"] != "blocked":
        # A wrong address or a missing page: nothing to scan. A blocked site still gets a report (below).
        return {"ok": False, "errors": site["errors"], "error_kind": site["error_kind"], "url": site["url"],
                "marketplace": site["marketplace"]}
    b = site["business"]
    # A typed name that looks like a web address ("Taqueriadediez") loses to the name the website states.
    typed = body.name.strip()
    found = (site.get("found_name") or "").strip()
    if found and typed and " " not in typed and typed.lower().replace("-", "") in body.url.lower().replace("-", ""):
        b["name"] = found
    if blocked and not b["segment"]:
        b["segment"] = "services"
    if not b["name"] or not b["city"]:
        return {"ok": False, "need": [k for k in ("name", "city") if not b[k]], "business": b, "url": site["url"],
                "blocked": blocked, "marketplace": site.get("marketplace", False)}
    cat, cat_es = CATEGORY.get(b["segment"], CATEGORY["services"])
    facts = [] if blocked else [{"label": f["label"], "label_es": f.get("label_es", ""), "value": f["value"],
                                 "category": f["category"], "evidence": "document", "source": f["source"]}
                                for f in site["suggested_facts"]]
    services_found = [] if blocked else site["found"]["services"][:3]
    req = {"name": b["name"], "category": cat, "category_es": cat_es, "segment": b["segment"], "city": b["city"],
           "website": site["url"], "competitors": [], "facts": facts, "services": services_found,
           "cuisine": None if blocked else site.get("cuisine"),
           "style": None if blocked else site.get("style"), "michelin": False if blocked else site.get("michelin")}
    check = services.run_check(req)
    check["site_score"] = None if blocked else site["score"]
    with get_db() as db:
        cid = db.execute("INSERT INTO checks (name, request, result, created_at) VALUES (?,?,?,?)",
                         (b["name"], json.dumps(req), json.dumps(check), now())).lastrowid
        if body.lead_id:
            db.execute("UPDATE leads SET check_id=? WHERE id=?", (cid, body.lead_id))
    # Missed opportunities: customer questions where AI named someone else more often than you.
    missed = [q for q in check["by_question"] if (q["rate"] or 0) < 50 and q["category"] != "About your business"]
    offered = {s["label"] for s in services_found}
    return {"ok": True, "check_id": cid, "business": b, "check": check, "site": site, "blocked": blocked,
            "missed": [dict(q, offered=q["category"] in offered) for q in missed]}


class CheckAnswer(BaseModel):
    provider: str = Field(max_length=20)
    language: str = "en"
    question: str = Field(min_length=3, max_length=300)
    text: str = Field(min_length=10, max_length=8000)


class CheckAnswers(BaseModel):
    answers: list[CheckAnswer] = Field(min_length=1, max_length=80)


@app.post("/api/check/{cid}/answers")
def check_pasted_answers(cid: int, body: CheckAnswers):
    """Replace a free report's simulated answers with real ones pasted from the free AI apps. $0 and real."""
    with get_db() as db:
        chk = row(db.execute("SELECT * FROM checks WHERE id=?", (cid,)))
        if not chk:
            raise HTTPException(404, "Check not found")
        req = json.loads(chk["request"])
        res = services.check_from_pasted(req, [a.model_dump() for a in body.answers])
        res["site_score"] = json.loads(chk["result"]).get("site_score")
        db.execute("UPDATE checks SET result=? WHERE id=?", (json.dumps(res), cid))  # leads now show the real numbers
        offered = {s["label"] for s in req.get("services") or []}
        missed = [q for q in res["by_question"] if (q["rate"] or 0) < 50 and q["category"] != "About your business"]
        return {"check": res, "missed": [dict(q, offered=q["category"] in offered) for q in missed]}


@app.post("/api/check/{cid}/start-trial", status_code=201)
def start_trial(cid: int):
    """Turns a free check into a business on the free trial, with the facts the owner typed."""
    with get_db() as db:
        chk = row(db.execute("SELECT * FROM checks WHERE id=?", (cid,)))
        if not chk:
            raise HTTPException(404, "Check not found")
        if chk["business_id"]:
            return {"id": chk["business_id"]}
        req = json.loads(chk["request"])
        comps = req["competitors"] or agents.DEFAULT_COMPETITORS.get(req["segment"], [])
        bid = db.execute(
            "INSERT INTO businesses (name, category, category_es, segment, city, website, competitors, plan, "
            "plan_started_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (req["name"], req["category"], req["category_es"], req["segment"], req["city"], req.get("website", ""),
             json.dumps(comps), "trial", now(), now())).lastrowid
        db.execute("UPDATE checks SET business_id=? WHERE id=?", (bid, cid))
        db.execute("UPDATE leads SET business_id=?, status='trial' WHERE check_id=?", (bid, cid))
        log(db, bid, "trial_started", req["name"], {"check_id": cid})
        if req["facts"]:
            _upsert_facts(db, bid, [FactIn(label=f["label"], label_es=f.get("label_es", ""), value=f["value"],
                                           category=f["category"], evidence=f.get("evidence", "owner"),
                                           key=agents.standard_key(f["category"], f["label"]) or None,
                                           source=f.get("source") or "Free AI Check (owner entry)") for f in req["facts"]],
                          "Owner (free check)")
            sales.ensure_history(db, services.load_business(db, bid))
            if agents.is_demo():
                services.run_scan(db, bid)
        return {"id": bid}


@app.post("/api/businesses", status_code=201)
def create_business(body: BusinessIn):
    if body.segment not in SEGMENTS:
        raise HTTPException(422, f"Segment must be one of {sorted(SEGMENTS)}")
    with get_db() as db:
        bid = db.execute(
            "INSERT INTO businesses (name, category, category_es, segment, city, website, competitors, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (body.name, body.category, body.category_es, body.segment, body.city, body.website,
             json.dumps(body.competitors), now())).lastrowid
        log(db, bid, "business_created", body.name)
        if body.facts:
            _upsert_facts(db, bid, body.facts, "Owner (onboarding)")
        sales.ensure_history(db, services.load_business(db, bid))
        return {"id": bid}


@app.put("/api/businesses/{bid}/sales")
def import_sales(bid: int, weeks: list[SalesWeek]):
    """Weekly AI-referred sales from Shopify / GA4 / Square exports, oldest week first."""
    with get_db() as db:
        _biz_or_404(db, bid)
        sales.import_weeks(db, bid, [w.model_dump() for w in weeks])
        log(db, bid, "sales_imported", "owner", {"weeks": len(weeks)})
        return sales.summary(db, bid)


class DeleteConfirm(BaseModel):
    confirm_name: str


@app.get("/api/businesses/{bid}/growth")
def growth(bid: int):
    with get_db() as db:
        _biz_or_404(db, bid)
        return services.growth_plan(db, bid)


@app.get("/api/businesses/{bid}/perception")
def get_perception(bid: int):
    with get_db() as db:
        _biz_or_404(db, bid)
        return services.perception(db, bid)


@app.get("/api/businesses/{bid}/insights")
def get_insights(bid: int):
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        if not plans.has(biz["plan"], "scan_history"):
            raise HTTPException(402, "What works is included in Silver and Gold.")
        return insights.insights(db, bid)


class Simulate(BaseModel):
    weeks: int = Field(6, ge=1, le=12)


@app.post("/api/businesses/{bid}/demo/simulate")
def simulate_weeks(bid: int, body: Simulate):
    """Demo only: runs weekly scans, approving up to two open fixes every other week as a labeled
    simulated owner, so trends and experiments have data. Every action lands in the audit log."""
    if not agents.is_demo():
        raise HTTPException(409, "Only available in demo mode")
    for week in range(body.weeks):
        if week % 2 == 0:
            with get_db() as db:
                _biz_or_404(db, bid)
                pick = lambda kind: rows(db.execute(  # noqa: E731
                    "SELECT id FROM incidents WHERE business_id=? AND type=? AND status IN ('open','needs_review') "
                    "ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, id LIMIT 1",
                    (bid, kind)))
                open_ = pick("wrong_fact") + pick("missed_opportunity")  # one of each: accuracy and visibility
            for inc in open_:
                try:
                    draft_fix(inc["id"])
                    approve(inc["id"], Approval(approver="Demo owner (simulated)"))
                except HTTPException:
                    break  # plan limit reached
        scan(bid)
    return {"ok": True}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list, max_length=12)
    lang: str = "en"


@app.post("/api/businesses/{bid}/chat")
def chat(bid: int, body: ChatIn):
    """AI Business Assistant: answers from this business's own results only."""
    with get_db() as db:
        _biz_or_404(db, bid)
        history = [{"role": str(m.get("role", ""))[:10], "content": str(m.get("content", ""))[:500]} for m in body.history]
        return assistant.answer(db, bid, body.message, history, body.lang)


# ------------------------------------------------------------ evidence

@app.post("/api/businesses/{bid}/verify-facts")
def verify_facts(bid: int):
    """Reads the business's website and the listings AI cites, and records what each says for every fact."""
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        return evidence.verify_facts(db, bid, services.load_facts(db, bid), biz)


@app.post("/api/incidents/{iid}/check-sources")
def check_sources(iid: int):
    """Opens the pages the assistant cited: did it copy a wrong page, or make it up?"""
    with get_db() as db:
        if not row(db.execute("SELECT id FROM incidents WHERE id=?", (iid,))):
            raise HTTPException(404, "Issue not found")
        return evidence.check_citations(db, iid)


@app.get("/api/incidents/{iid}/evidence")
def evidence_report(iid: int):
    with get_db() as db:
        rep = evidence.report(db, iid)
        if not rep:
            raise HTTPException(404, "Issue not found")
        log(db, row(db.execute("SELECT business_id FROM incidents WHERE id=?", (iid,)))["business_id"],
            "evidence_exported", "owner", {"incident_id": iid})
        return rep


class LabelIn(BaseModel):
    reviewer: str = Field(min_length=1, max_length=80)
    human_verdict: str


@app.get("/api/businesses/{bid}/labeling/next")
def next_to_label(bid: int):
    """A random checked claim nobody has reviewed yet, for 'check the checker'."""
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        facts = {f["key"]: f for f in services.load_facts(db, bid)}
        c = row(db.execute(
            "SELECT c.*, r.text, r.provider, j.question FROM claims c JOIN responses r ON r.id=c.response_id "
            "JOIN journeys j ON j.id=r.journey_id JOIN scans s ON s.id=r.scan_id WHERE s.business_id=? "
            "AND c.id NOT IN (SELECT claim_id FROM labels) ORDER BY RANDOM() LIMIT 1", (bid,)))
        stats = evidence.checker_accuracy(db, bid)
        if not c:
            return {"claim": None, "stats": stats}
        f = facts.get(c["fact_key"], {})
        from .reader import business_segment
        return {"stats": stats, "claim": {
            "id": c["id"], "assistant": c["provider"], "question": c["question"], "fact": f.get("label", c["fact_key"]),
            "category": f.get("category"), "truth": f.get("value"), "ai_value": c["value"], "checker": c["verdict"],
            "excerpt": business_segment(c["text"], biz["name"])[2].strip()[:500]}}


@app.post("/api/claims/{cid}/label")
def label_claim(cid: int, body: LabelIn):
    if body.human_verdict not in ("match", "wrong", "unclear"):
        raise HTTPException(422, "human_verdict must be match, wrong or unclear")
    with get_db() as db:
        c = row(db.execute("SELECT s.business_id FROM claims c JOIN responses r ON r.id=c.response_id "
                           "JOIN scans s ON s.id=r.scan_id WHERE c.id=?", (cid,)))
        if not c:
            raise HTTPException(404, "Claim not found")
        db.execute("INSERT INTO labels (claim_id, reviewer, human_verdict, created_at) VALUES (?,?,?,?)",
                   (cid, body.reviewer.strip(), body.human_verdict, now()))
        log(db, c["business_id"], "claim_labeled", body.reviewer.strip(), {"claim_id": cid, "verdict": body.human_verdict})
        return evidence.checker_accuracy(db, c["business_id"])


# ------------------------------------------------------------ $0 scans, real bookings, proof lab

class PastedAnswer(BaseModel):
    provider: str = Field(max_length=20)
    language: str = "en"
    question: str = Field(min_length=3, max_length=300)
    text: str = Field(min_length=10, max_length=8000)
    sources: list[str] = Field(default_factory=list, max_length=20)


class ManualScan(BaseModel):
    answers: list[PastedAnswer] = Field(min_length=1, max_length=60)


@app.post("/api/businesses/{bid}/manual-scan")
def manual_scan(bid: int, body: ManualScan):
    """Answers copied from the free ChatGPT / Gemini / Perplexity / Copilot apps, checked like any scan."""
    with get_db() as db:
        _biz_or_404(db, bid)
        if not services.load_facts(db, bid):
            raise HTTPException(422, "Add and confirm at least one verified fact first")
        return services.manual_scan(db, bid, [a.model_dump() for a in body.answers])


class ReferralWeek(BaseModel):
    week_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    total_jobs: int = Field(ge=0, le=100000)
    ai_jobs: int = Field(ge=0, le=100000)
    ai_revenue: float | None = Field(default=None, ge=0)


@app.put("/api/businesses/{bid}/referrals")
def log_referrals(bid: int, body: ReferralWeek):
    """'How did you hear about us?' counts, logged by the owner each week. Real, and free."""
    if body.ai_jobs > body.total_jobs:
        raise HTTPException(422, "AI jobs can't be more than total jobs")
    with get_db() as db:
        _biz_or_404(db, bid)
        db.execute("INSERT INTO referral_log (business_id, week_start, total_jobs, ai_jobs, ai_revenue, created_at) "
                   "VALUES (?,?,?,?,?,?) ON CONFLICT(business_id, week_start) DO UPDATE SET total_jobs=excluded.total_jobs, "
                   "ai_jobs=excluded.ai_jobs, ai_revenue=excluded.ai_revenue",
                   (bid, body.week_start, body.total_jobs, body.ai_jobs, body.ai_revenue, now()))
        log(db, bid, "referrals_logged", "owner", body.model_dump())
        return rows(db.execute("SELECT * FROM referral_log WHERE business_id=? ORDER BY week_start", (bid,)))


class LabRun(BaseModel):
    repeats: int = Field(3, ge=1, le=5)


@app.post("/api/businesses/{bid}/proof-lab")
def run_proof_lab(bid: int, body: LabRun):
    with get_db() as db:
        _biz_or_404(db, bid)
        res = prooflab.run(db, bid, body.repeats)
        log(db, bid, "proof_lab_run", "owner", {"run_id": res["id"], "mode": res["mode"]})
        return res


@app.get("/api/businesses/{bid}/proof-lab")
def get_proof_lab(bid: int):
    with get_db() as db:
        _biz_or_404(db, bid)
        return prooflab.latest(db, bid)


@app.get("/api/businesses/{bid}/proof-lab.csv", response_class=PlainTextResponse)
def proof_lab_csv(bid: int):
    with get_db() as db:
        r = prooflab.latest(db, bid)
        if not r:
            raise HTTPException(404, "Run the Proof Lab first")
        return PlainTextResponse(prooflab.csv_text(r), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=proof-lab-{bid}.csv"})


class SiteItem(BaseModel):
    name: str = Field(max_length=120)
    name_es: str = Field("", max_length=120)
    price: str = Field("", max_length=20)


class SiteAuditIn(BaseModel):
    url: str = Field(min_length=4, max_length=300)
    name: str = Field("", max_length=120)
    city: str = Field("", max_length=120)
    segment: str = "cleaning"
    items: list[SiteItem] = Field(default_factory=list, max_length=60)
    business_id: int | None = None


@app.post("/api/site-audit")
def run_site_audit(body: SiteAuditIn):
    """Website check: how an AI assistant reads this site, what's missing, and ready-to-paste fixes. No key needed."""
    if not re.match(r"^(https?://)?[a-z0-9.-]+\.[a-z]{2,}(/\S*)?$", body.url.strip(), re.I):
        raise HTTPException(422, "Enter a website address like brillocleaning.com")
    with get_db() as db:
        res = site_audit.audit(db, body.url, body.name, body.city, body.segment,
                               [i.model_dump() for i in body.items], body.business_id)
        if body.business_id:
            log(db, body.business_id, "site_checked", "owner", {"url": res.get("url"), "score": res.get("score")})
        return res


@app.get("/api/businesses/{bid}/export")
def export_data(bid: int):
    """Data portability: the owner can take everything with them at any time."""
    with get_db() as db:
        _biz_or_404(db, bid)
        log(db, bid, "data_exported", "owner")
        return services.export_all(db, bid)


@app.delete("/api/businesses/{bid}")
def delete_business(bid: int, body: DeleteConfirm):
    """Right to delete: removes the business and everything tied to it, including its audit log."""
    with get_db() as db:
        biz = _biz_or_404(db, bid)
        if body.confirm_name.strip() != biz["name"]:
            raise HTTPException(422, "Type the business name exactly to confirm")
        db.execute("DELETE FROM audit_log WHERE business_id=?", (bid,))
        db.execute("DELETE FROM businesses WHERE id=?", (bid,))  # facts, scans, answers, issues, sales cascade
        return {"ok": True}


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
            r["descriptors"] = json.loads(r.get("descriptors") or "[]")
            r["sources"] = rows(db.execute("SELECT url, domain FROM sources WHERE response_id=?", (r["id"],)))
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
        limit = plans.get(biz["plan"])["fix_drafts"]
        used = db.execute("SELECT COUNT(*) FROM incidents WHERE business_id=? AND suggested_fix IS NOT NULL",
                          (biz["id"],)).fetchone()[0]
        if limit is not None and not inc["suggested_fix"] and used >= limit:
            raise HTTPException(402, f"The free trial includes {limit} fix drafts. Upgrade to Silver for unlimited fixes.")
        fix = agents.generate_fix(inc, biz, fact)
        if inc["fact_key"]:
            fix["likely_source"] = services.likely_source(db, inc["business_id"], inc["fact_key"], inc["provider"])
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
        last = row(db.execute("SELECT MAX(id) AS id FROM scans WHERE business_id=?", (inc["business_id"],)))
        db.execute("UPDATE incidents SET status='approved', approved_by=?, approved_at=?, approved_after_scan=? "
                   "WHERE id=?", (body.approver.strip(), now(), last["id"], iid))
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
