"""Pipeline: journeys -> ask assistants -> extract claims -> validate -> incidents -> metrics."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import agents, evidence, plans, reader, sales
from .db import log, now, row, rows
from .validator import effective_evidence, severity_for, values_match, verdict

ACTIVE = ("open", "needs_review", "approved")
MISSED_THRESHOLD = 0.5


def load_business(db, business_id: int) -> dict | None:
    biz = row(db.execute("SELECT * FROM businesses WHERE id=?", (business_id,)))
    if biz:
        biz["competitors"] = json.loads(biz["competitors"])
    return biz


def load_facts(db, business_id: int) -> list[dict]:
    facts = rows(db.execute("SELECT * FROM facts WHERE business_id=? ORDER BY product = '', product, category, key",
                            (business_id,)))
    conf = evidence.fact_confirmations(db, business_id)
    for f in facts:
        f["effective_evidence"] = effective_evidence(f)
        c = conf.get(f["key"], {"agree": [], "disagree": []})
        f["confirmed_by"], f["disagreeing"] = c["agree"], c["disagree"]
        # Two independent pages agreeing lifts an owner-only fact to 'confirmed'
        if f["effective_evidence"] in ("owner", "expired") and len(c["agree"]) >= 2:
            f["effective_evidence"] = "confirmed"
    return facts


def plan_providers(biz: dict) -> list[str]:
    limit = plans.get(biz.get("plan"))["assistants"]
    return agents.providers()[:limit] if limit else agents.providers()


def ensure_journeys(db, biz: dict, facts: list[dict], regenerate: bool = False) -> list[dict]:
    if regenerate:
        db.execute("DELETE FROM journeys WHERE business_id=?", (biz["id"],))
    js = rows(db.execute("SELECT * FROM journeys WHERE business_id=?", (biz["id"],)))
    if not js:
        for j in agents.generate_journeys(biz, facts):
            db.execute("INSERT INTO journeys (business_id, question, language, category, related_facts) "
                       "VALUES (?,?,?,?,?)", (biz["id"], j["question"], j["language"], j["category"],
                                              json.dumps(j.get("related_facts", []))))
        log(db, biz["id"], "journeys_generated", "system")
        js = rows(db.execute("SELECT * FROM journeys WHERE business_id=?", (biz["id"],)))
    for j in js:
        j["related_facts"] = json.loads(j["related_facts"] or "[]")
    return js


def run_scan(db, business_id: int) -> dict:
    biz = load_business(db, business_id)
    facts = load_facts(db, business_id)
    by_key = {f["key"]: f for f in facts}
    journeys = ensure_journeys(db, biz, facts)[:plans.get(biz.get("plan"))["journeys"]]
    demo = agents.is_demo()

    scan_round = db.execute("SELECT COUNT(*) FROM scans WHERE business_id=?", (business_id,)).fetchone()[0]
    fixed = rows(db.execute(
        "SELECT type, fact_key, category, language FROM incidents WHERE business_id=? "
        "AND status IN ('approved','resolved')", (business_id,)))
    fixed_keys = {i["fact_key"] for i in fixed if i["type"] == "wrong_fact"}
    fixed_missed = {(i["category"], i["language"]) for i in fixed if i["type"] == "missed_opportunity"}

    scan_id = db.execute("INSERT INTO scans (business_id, mode, created_at) VALUES (?,?,?)",
                         (business_id, "demo" if demo else "live", now())).lastrowid
    errors = []
    for j in journeys:
        for p in plan_providers(biz):
            try:
                if demo:
                    text, ext = agents.simulate(p, j, biz, facts, biz["competitors"], scan_round,
                                                fixed_keys, fixed_missed)
                else:
                    city = "" if agents.is_shop(biz) else biz["city"]
                    text, cited = agents.ask_assistant(p, j["question"], city)
                    ext = agents.extract(text, biz, facts, biz["competitors"])
                    ext["sources"] = cited
            except Exception as e:  # one failed call shouldn't sink the scan
                errors.append(f"{p}: {e}")
                continue
            model = "simulated" if demo else agents.model_for(p)
            store_response(db, scan_id, j["id"], p, text, ext, model, by_key)

    _update_incidents(db, biz, by_key, scan_id)
    sales.record_scan_week(db, biz, _scan_metrics(db, scan_id, facts))
    if demo:  # live checks fetch real pages, so they run when a person asks (Issues → Check sources)
        for inc in rows(db.execute("SELECT id FROM incidents WHERE business_id=? AND type='wrong_fact' AND origin IS NULL "
                                   "AND status IN ('open','needs_review')", (business_id,))):
            evidence.check_citations(db, inc["id"])
    log(db, business_id, "scan_completed", "system", {"scan_id": scan_id, "mode": "demo" if demo else "live",
                                                      "errors": errors})
    return {"scan_id": scan_id, "mode": "demo" if demo else "live", "errors": errors}


def store_response(db, scan_id, journey_id, provider, text, ext, model, by_key):
    """Saves one AI answer exactly as received, the pages it cited, and each claim with the checker's verdict."""
    rid = db.execute(
        "INSERT INTO responses (scan_id, journey_id, provider, text, mentioned, position, competitors, "
        "description, descriptors, sentiment, model) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (scan_id, journey_id, provider, text, int(ext["mentioned"]), ext.get("position"),
         json.dumps(ext.get("competitors", [])), ext.get("description") or "",
         json.dumps(ext.get("descriptors") or [], ensure_ascii=False), ext.get("sentiment"), model)).lastrowid
    for src in {s["url"]: s for s in ext.get("sources") or []}.values():
        db.execute("INSERT INTO sources (response_id, url, domain, title) VALUES (?,?,?,?)",
                   (rid, src["url"], agents.domain_of(src["url"]), src.get("title") or ""))
    for c in ext.get("claims", []):
        fact = by_key.get(c.get("fact_key"))
        if fact and c.get("value") not in (None, ""):
            db.execute("INSERT INTO claims (response_id, fact_key, value, verdict) VALUES (?,?,?,?)",
                       (rid, fact["key"], str(c["value"]), verdict(fact, str(c["value"]))))
    return rid


def manual_scan(db, business_id: int, answers: list[dict]) -> dict:
    """Answers pasted from the free consumer apps (ChatGPT, Gemini, Perplexity, Copilot). $0, and it's exactly
    what customers see. Read with code (or the extractor when keys are set), then checked like any scan."""
    biz = load_business(db, business_id)
    facts = load_facts(db, business_id)
    by_key = {f["key"]: f for f in facts}
    # Answers pasted on the same day add up to one scan, so a team pasting 40 answers gets one 40-answer scan.
    last = row(db.execute("SELECT * FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    if last and last["mode"] == "manual" and last["created_at"][:10] == now()[:10]:
        scan_id = last["id"]
    else:
        scan_id = db.execute("INSERT INTO scans (business_id, mode, created_at) VALUES (?,?,?)",
                             (business_id, "manual", now())).lastrowid
    for a in answers:
        j = row(db.execute("SELECT id FROM journeys WHERE business_id=? AND question=?", (business_id, a["question"])))
        jid = j["id"] if j else db.execute(
            "INSERT INTO journeys (business_id, question, language, category, related_facts) VALUES (?,?,?,?,?)",
            (business_id, a["question"], a["language"], a.get("category") or "Pasted question", "[]")).lastrowid
        ext = reader.read_answer(a["text"], biz, facts, biz["competitors"])
        if not agents.is_demo():
            try:  # with keys, the AI extractor also reads descriptions and tone
                ext = {**agents.extract(a["text"], biz, facts, biz["competitors"]), "sources": ext["sources"]}
            except Exception:
                pass
        ext["sources"] += [{"url": u, "title": ""} for u in a.get("sources") or []]
        store_response(db, scan_id, jid, a["provider"], a["text"], ext, "consumer app (pasted)", by_key)
    _update_incidents(db, biz, by_key, scan_id)
    log(db, business_id, "manual_scan", "owner", {"scan_id": scan_id, "answers": len(answers)})
    return {"scan_id": scan_id, "answers": len(answers)}


def _update_incidents(db, biz, by_key, scan_id):
    bid = biz["id"]
    claims = rows(db.execute(
        "SELECT c.*, r.provider FROM claims c JOIN responses r ON r.id=c.response_id WHERE r.scan_id=?",
        (scan_id,)))

    # Wrong facts: one incident per (fact, assistant) while it stays active.
    grouped = defaultdict(list)
    for c in claims:
        grouped[(c["fact_key"], c["provider"])].append(c)
    for (key, provider), cs in grouped.items():
        bad = [c for c in cs if c["verdict"] != "match"]
        existing = row(db.execute(
            f"SELECT * FROM incidents WHERE business_id=? AND type='wrong_fact' AND fact_key=? AND provider=? "
            f"AND status IN {ACTIVE}", (bid, key, provider)))
        if not bad and existing and existing["status"] == "approved":
            db.execute("UPDATE incidents SET status='resolved', resolved_at=? WHERE id=?", (now(), existing["id"]))
            log(db, bid, "incident_resolved", "system", {"incident_id": existing["id"], "scan_id": scan_id})
        elif bad and not existing:
            fact = by_key[key]
            v = Counter(c["value"] for c in bad).most_common(1)[0][0]
            status = "open" if any(c["verdict"] == "wrong" for c in bad) else "needs_review"
            db.execute(
                "INSERT INTO incidents (business_id, scan_id, type, fact_key, provider, ai_value, verified_value, "
                "detail, severity, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (bid, scan_id, "wrong_fact", key, provider, v, fact["value"],
                 f"Seen in {len(bad)} of {len(cs)} answers", severity_for(fact), status, now()))

    # Missed opportunities: a customer need where competitors get named and we don't.
    resp = rows(db.execute(
        "SELECT r.*, j.category, j.language FROM responses r JOIN journeys j ON j.id=r.journey_id "
        "WHERE r.scan_id=?", (scan_id,)))
    buckets = defaultdict(list)
    for r in resp:
        buckets[(r["category"], r["language"])].append(r)
    for (cat, lang), rs in buckets.items():
        missed = [r for r in rs if not r["mentioned"] and json.loads(r["competitors"])]
        rate = len(missed) / len(rs)
        existing = row(db.execute(
            f"SELECT * FROM incidents WHERE business_id=? AND type='missed_opportunity' AND category=? "
            f"AND language=? AND status IN {ACTIVE}", (bid, cat, lang)))
        if rate <= MISSED_THRESHOLD and existing and existing["status"] == "approved":
            db.execute("UPDATE incidents SET status='resolved', resolved_at=? WHERE id=?", (now(), existing["id"]))
            log(db, bid, "incident_resolved", "system", {"incident_id": existing["id"], "scan_id": scan_id})
        elif rate > MISSED_THRESHOLD and not existing:
            comps = Counter(c for r in missed for c in json.loads(r["competitors"])).most_common(2)
            db.execute(
                "INSERT INTO incidents (business_id, scan_id, type, category, language, detail, severity, status, "
                "created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (bid, scan_id, "missed_opportunity", cat, lang,
                 f"Missed in {len(missed)} of {len(rs)} answers. Recommended instead: "
                 f"{', '.join(c for c, _ in comps)}.", "medium", "open", now()))


def _scan_metrics(db, scan_id: int, facts: list[dict] | None = None) -> dict:
    resp = rows(db.execute(
        "SELECT r.*, j.category, j.language FROM responses r JOIN journeys j ON j.id=r.journey_id "
        "WHERE r.scan_id=?", (scan_id,)))
    claims = rows(db.execute(
        "SELECT c.* FROM claims c JOIN responses r ON r.id=c.response_id WHERE r.scan_id=?", (scan_id,)))

    def rate(rs):
        return round(100 * sum(r["mentioned"] for r in rs) / len(rs)) if rs else None

    en = [r for r in resp if r["language"] == "en"]
    es = [r for r in resp if r["language"] == "es"]
    judged = [c for c in claims if c["verdict"] != "needs_review"]
    by_cat = defaultdict(list)
    for r in resp:
        by_cat[r["category"]].append(r)
    by_provider = defaultdict(list)
    for r in resp:
        by_provider[r["provider"]].append(r)
    product_of = {f["key"]: f.get("product") or "" for f in (facts or [])}
    per_product = defaultdict(list)
    for c in judged:
        if product_of.get(c["fact_key"]):
            per_product[product_of[c["fact_key"]]].append(c)
    return {
        "product_accuracy": sorted(
            ({"product": k, "accuracy": round(100 * sum(c["verdict"] == "match" for c in v) / len(v)),
              "checked": len(v)} for k, v in per_product.items()), key=lambda x: x["accuracy"]),
        "responses": len(resp),
        "inclusion_rate": rate(resp),
        "inclusion_en": rate(en),
        "inclusion_es": rate(es),
        "language_gap": (rate(en) - rate(es)) if en and es else None,
        "fact_accuracy": round(100 * sum(c["verdict"] == "match" for c in judged) / len(judged)) if judged else None,
        "claims_checked": len(claims),
        "missed_opportunities": sum(1 for r in resp if not r["mentioned"] and json.loads(r["competitors"])),
        "by_need": sorted(({"need": k, "inclusion": rate(v), "answers": len(v)} for k, v in by_cat.items()),
                          key=lambda x: x["inclusion"]),
        "by_assistant": {k: rate(v) for k, v in by_provider.items()},
    }


def dashboard(db, business_id: int) -> dict:
    biz = load_business(db, business_id)
    facts = load_facts(db, business_id)
    scans = rows(db.execute("SELECT * FROM scans WHERE business_id=? ORDER BY id", (business_id,)))
    incidents = list_incidents(db, business_id)
    resolved = [i for i in incidents if i["resolved_at"]]
    hours = [(datetime.fromisoformat(i["resolved_at"]) - datetime.fromisoformat(i["created_at"])).total_seconds()
             / 3600 for i in resolved]
    plan = plans.get(biz.get("plan"))
    has = lambda f: f in plan["features"]  # noqa: E731
    locked_missed = 0
    if not has("missed_opportunities"):
        locked_missed = sum(1 for i in incidents if i["type"] == "missed_opportunity" and i["status"] in ACTIVE)
        incidents = [i for i in incidents if i["type"] != "missed_opportunity"]
    out = {"business": biz, "facts": facts, "scans": [], "latest": None, "matrix": [],
           "providers": plan_providers(biz), "mode": "demo" if agents.is_demo() else "live",
           "incidents": incidents, "sales": _gated_sales(db, business_id, has),
           "checker": evidence.checker_accuracy(db, business_id),
           "referrals": rows(db.execute("SELECT * FROM referral_log WHERE business_id=? ORDER BY week_start",
                                        (business_id,))),
           "plan": _plan_status(db, biz, plan), "locked_missed": locked_missed,
           "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None}
    for s in scans:
        m = _scan_metrics(db, s["id"], facts)
        out["scans"].append({"id": s["id"], "created_at": s["created_at"], "mode": s["mode"],
                             "inclusion_rate": m["inclusion_rate"], "fact_accuracy": m["fact_accuracy"],
                             "inclusion_es": m["inclusion_es"]})
    if not has("scan_history"):
        out["scans"] = out["scans"][-1:]
    if not scans:
        return out
    last = scans[-1]["id"]
    out["latest"] = _scan_metrics(db, last, facts)
    if not has("product_accuracy"):
        out["latest"]["product_accuracy"] = []
    if has("guarantee"):
        out["plan"]["guarantee"] = _guarantee(biz, out["latest"]["fact_accuracy"])

    # "What's true vs. what AI says": latest claim per fact per assistant.
    claims = rows(db.execute(
        "SELECT c.*, r.provider FROM claims c JOIN responses r ON r.id=c.response_id WHERE r.scan_id=? "
        "ORDER BY c.id", (last,)))
    seen = defaultdict(dict)
    for c in claims:
        prev = seen[c["fact_key"]].get(c["provider"])
        if not prev or prev["verdict"] == "match":  # surface a problem if any answer had one
            seen[c["fact_key"]][c["provider"]] = {"value": c["value"], "verdict": c["verdict"]}
    for f in facts:
        out["matrix"].append({"key": f["key"], "label": f["label"], "label_es": f["label_es"],
                              "product": f["product"], "product_es": f["product_es"], "category": f["category"],
                              "value": f["value"], "evidence": f["effective_evidence"],
                              "confirmed_by": f["confirmed_by"], "disagreeing": f["disagreeing"],
                              "assistants": seen.get(f["key"], {})})
    return out


def _plan_status(db, biz: dict, plan: dict) -> dict:
    started = datetime.fromisoformat(biz.get("plan_started_at") or biz["created_at"])
    used = db.execute("SELECT COUNT(*) FROM incidents WHERE business_id=? AND suggested_fix IS NOT NULL",
                      (biz["id"],)).fetchone()[0]
    out = {**plan, "fix_drafts_used": used}
    if plan["id"] == "trial":
        out["trial_days_left"] = max(0, plans.TRIAL_DAYS - (datetime.now(timezone.utc) - started).days)
    return out


def _guarantee(biz: dict, accuracy) -> dict:
    started = datetime.fromisoformat(biz.get("plan_started_at") or biz["created_at"])
    day = (datetime.now(timezone.utc) - started).days + 1
    target, days = plans.GUARANTEE["accuracy"], plans.GUARANTEE["days"]
    return {"target": target, "days": days, "day": min(day, days), "accuracy": accuracy,
            "deadline": (started + timedelta(days=days)).date().isoformat(),
            "met": accuracy is not None and accuracy >= target}


def _gated_sales(db, business_id: int, has) -> dict | None:
    if not has("sales_basic"):
        return None
    s = sales.summary(db, business_id)
    if s and not has("sales_full"):
        for k in ("extra_revenue", "revenue_lift", "lost_revenue_last", "misinfo_contacts_last",
                  "misinfo_contacts_start"):
            s[k] = None
        s["weeks"] = [{**w, "expected_revenue": None, "lost_revenue": None, "misinfo_contacts": None}
                      for w in s["weeks"]]
        s["locked"] = True
    return s


def _source_stats(db, business_id: int, scan_id: int, biz: dict) -> list[dict]:
    """Which pages the assistants relied on, and how often answers citing them got facts wrong.

    This is correlation, not proof: a source is flagged as a likely cause when most answers citing it
    contain a wrong fact. A person confirms before anyone contacts that site.
    """
    cites = rows(db.execute(
        "SELECT s.domain, s.url, r.id AS rid, r.provider FROM sources s JOIN responses r ON r.id=s.response_id "
        "WHERE r.scan_id=?", (scan_id,)))
    wrong = {r["response_id"]: r["n"] for r in rows(db.execute(
        "SELECT c.response_id, COUNT(*) AS n FROM claims c JOIN responses r ON r.id=c.response_id "
        "WHERE r.scan_id=? AND c.verdict='wrong' GROUP BY c.response_id", (scan_id,)))}
    by = defaultdict(lambda: {"answers": set(), "wrong": set(), "assistants": set(), "url": ""})
    for c in cites:
        d = by[c["domain"]]
        d["answers"].add(c["rid"]); d["assistants"].add(c["provider"]); d["url"] = d["url"] or c["url"]
        if c["rid"] in wrong:
            d["wrong"].add(c["rid"])
    out = []
    for domain, d in by.items():
        kind, label = agents.classify_source(domain, biz)
        share = round(100 * len(d["wrong"]) / len(d["answers"]))
        out.append({"domain": domain, "url": d["url"], "kind": kind, "label": label, "cited": len(d["answers"]),
                    "wrong_share": share, "assistants": sorted(d["assistants"]),
                    "likely_cause": share >= 60 and len(d["answers"]) >= 2 and kind != "own"})
    return sorted(out, key=lambda x: (-x["likely_cause"], -x["cited"]))


def likely_source(db, business_id: int, fact_key: str, provider: str | None) -> dict | None:
    """The page most often cited by answers that got this fact wrong (latest scan)."""
    last = row(db.execute("SELECT id FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    if not last:
        return None
    q = ("SELECT s.domain, s.url, COUNT(*) AS n FROM claims c JOIN responses r ON r.id=c.response_id "
         "JOIN sources s ON s.response_id=r.id WHERE r.scan_id=? AND c.fact_key=? AND c.verdict!='match' ")
    args = [last["id"], fact_key]
    if provider:
        q += "AND r.provider=? "
        args.append(provider)
    hits = rows(db.execute(q + "GROUP BY s.domain ORDER BY n DESC", args))
    biz = load_business(db, business_id)
    for h in hits:
        kind, label = agents.classify_source(h["domain"], biz)
        if kind != "own":
            return {"domain": h["domain"], "url": h["url"], "label": label, "kind": kind, "answers": h["n"]}
    return None


def perception(db, business_id: int) -> dict | None:
    """How AI assistants understand the business: descriptions, associations, beliefs, tone, and sources."""
    biz = load_business(db, business_id)
    facts = {f["key"]: f for f in load_facts(db, business_id)}
    last = row(db.execute("SELECT id FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    if not last:
        return None
    resp = rows(db.execute("SELECT * FROM responses WHERE scan_id=?", (last["id"],)))
    claims = rows(db.execute(
        "SELECT c.*, r.provider FROM claims c JOIN responses r ON r.id=c.response_id WHERE r.scan_id=?", (last["id"],)))
    assistants = []
    words_all = Counter()
    for p in dict.fromkeys(r["provider"] for r in resp):
        rs = [r for r in resp if r["provider"] == p]
        named = [r for r in rs if r["mentioned"]]
        words = Counter(w for r in named for w in json.loads(r.get("descriptors") or "[]"))
        words_all.update(words)
        tone = Counter(r.get("sentiment") or "neutral" for r in named)
        beliefs = {}
        for c in (c for c in claims if c["provider"] == p):
            prev = beliefs.get(c["fact_key"])
            if not prev or prev["verdict"] == "match":  # surface a wrong belief if any answer had one
                beliefs[c["fact_key"]] = {"value": c["value"], "verdict": c["verdict"]}
        positions = [r["position"] for r in named if r["position"]]
        descs = [r["description"] for r in named if r.get("description")]
        assistants.append({
            "provider": p, "answers": len(rs), "named": len(named),
            "inclusion": round(100 * len(named) / len(rs)) if rs else 0,
            "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
            "description": Counter(descs).most_common(1)[0][0] if descs else "",
            "descriptors": [w for w, _ in words.most_common(5)],
            "tone": tone.most_common(1)[0][0] if tone else None,
            "beliefs": [{"key": k, "label": facts[k]["label"] if k in facts else k,
                         "product": facts[k].get("product", "") if k in facts else "",
                         "category": facts[k]["category"] if k in facts else "", "truth": facts[k]["value"] if k in facts else "",
                         **v} for k, v in beliefs.items()],
        })
    fact_words = {w.lower() for f in facts.values() for w in (f["label"], f.get("label_es") or "")}
    return {
        "assistants": assistants,
        "associations": [{"word": w, "count": n} for w, n in words_all.most_common(12)],
        "sources": _source_stats(db, business_id, last["id"], biz),
        "never_mentioned": [f["label"] for k, f in facts.items() if not any(c["fact_key"] == k for c in claims)],
        "fact_words": sorted(fact_words),
    }


GROWTH_WEEKS = 12  # point B is 90 days out
RAMP_WEEKS = 8


def growth_plan(db, business_id: int) -> dict | None:
    """Point A (measured today) -> point B (90-day target), the steps between, and projected AI-referred sales."""
    biz = load_business(db, business_id)
    facts = load_facts(db, business_id)
    last = row(db.execute("SELECT id FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    if not last:
        return None
    m = _scan_metrics(db, last["id"], facts)
    plan = plans.get(biz.get("plan"))
    acc, inc = m["fact_accuracy"] or 0, m["inclusion_rate"] or 0
    es = m["inclusion_es"] if m["inclusion_es"] is not None else inc
    a = {"inclusion": inc, "accuracy": acc, "inclusion_es": es}
    b = {"accuracy": max(acc, 95), "inclusion": max(inc, min(inc + 25, 85))}
    b["inclusion_es"] = max(es, b["inclusion"] - 5)

    active = [i for i in list_incidents(db, business_id) if i["status"] in ("open", "needs_review")]
    urgent = [i for i in active if i["type"] == "wrong_fact" and i["severity"] in ("critical", "high")]
    other = [i for i in active if i["type"] in ("wrong_fact", "source_conflict") and i not in urgent]
    missed = [i for i in active if i["type"] == "missed_opportunity"]
    weak = [f for f in facts if f["effective_evidence"] in ("owner", "expired")]
    gap = (m["inclusion_en"] or 0) - (m["inclusion_es"] or 0)
    steps = [
        {"id": "critical", "weeks": "1-2", "count": len(urgent), "done": not urgent},
        {"id": "facts", "weeks": "2-4", "count": len(other) + len(weak), "done": not other and not weak},
        {"id": "spanish", "weeks": "3-6", "count": max(gap, 0), "done": gap < 10},
        {"id": "missed", "weeks": "4-10", "count": len(missed) if "missed_opportunities" in plan["features"] else None,
         "done": not missed},
        {"id": "keep", "weeks": "ongoing", "count": None, "done": False},
    ]
    for st in steps:
        st["evidence"] = []
    ev = {st["id"]: st["evidence"] for st in steps}
    ev["spanish"].append({"id": "es_gap", "es": m["inclusion_es"], "en": m["inclusion_en"]})
    if missed:
        ev["missed"].append({"id": "missed_now", "n": len(missed)})
    if "scan_history" in plan["features"]:
        from .insights import insights  # imported here: insights depends on this module
        ins = insights(db, business_id)
        sig = {x["id"]: x for x in ins.get("signals", [])}
        exp_acc = [e for e in ins.get("experiments", []) if e["metric"] == "accuracy" and e["lift"] > 0]
        exp_inc = [e for e in ins.get("experiments", []) if e["metric"] == "inclusion" and e["lift"] > 0]
        if exp_acc:
            e = exp_acc[0]
            ev["critical"].append({"id": "fix_worked", "label": e["label"], "before": e["before"], "after": e["after"],
                                   "lift": e["lift"]})
        if "source:own" in sig:
            ev["facts"].append({"id": "own_site", "with": sig["source:own"]["with"], "without": sig["source:own"]["without"]})
        if exp_inc:
            e = exp_inc[0]
            ev["missed"].append({"id": "missed_worked", "label": e["label"], "before": e["before"], "after": e["after"],
                                 "lift": e["lift"]})
        d = sig.get("source:directory")
        if d and d["wrong_with"] is not None and d["wrong_without"] is not None:
            ev["keep"].append({"id": "stale_source", "with": d["wrong_with"], "without": d["wrong_without"]})

    out = {"a": a, "b": b, "steps": steps, "weeks": GROWTH_WEEKS, "projection": None,
           "plan_price": plan["price"], "assumptions": {
               "ai_growth_week": round((sales.AI_TREND - 1) * 100, 1),
               "search_change_week": round((sales.SEARCH_TREND - 1) * 100, 1),
               "wrong_fact_loss": 65, "ramp_weeks": RAMP_WEEKS}}
    s = sales.summary(db, business_id)
    if s and "sales_basic" in plan["features"]:
        start = s["weeks"][-1]["week"]
        proj = sales.project(biz, start, GROWTH_WEEKS, a, b, RAMP_WEEKS)
        for p in proj:  # range: the plan delivers half (slow) to 1.3x (fast) of the expected effect
            gain = p["plan"] - p["stay"]
            p["low"], p["high"] = round(p["stay"] + 0.5 * gain, 2), round(p["stay"] + 1.3 * gain, 2)
        out["projection"] = proj
        aov = sales.PROFILES.get(biz.get("segment"), sales.PROFILES["services"])["aov"]
        extra = lambda k: round(sum(p[k] - p["stay"] for p in proj))  # noqa: E731
        month3 = sum(p["plan"] - p["stay"] for p in proj[-4:]) * 4.33 / 4
        out.update({
            "aov": aov,
            "extra_90_days": extra("plan"), "extra_90_low": extra("low"), "extra_90_high": extra("high"),
            "extra_month3": round(month3), "extra_jobs_month3": round(month3 / aov, 1),
        })
        out["a"]["revenue_week"] = s["weeks"][-1]["ai_revenue"]
        out["b"]["revenue_week"] = proj[-1]["plan"]
        # Where the growth comes from: apply each step in order at month 3, in the same market conditions.
        wk = proj[-1]["week"]
        rev = lambda inc, acc: sales.revenue_at(biz, wk, inc, acc) * 4.33  # noqa: E731
        share = len(urgent) / (len(urgent) + len(other) + len(weak)) if (urgent or other or weak) else 0.5
        acc_mid = a["accuracy"] + (b["accuracy"] - a["accuracy"]) * share
        sp = min(b["inclusion"] - a["inclusion"], max(0, b["inclusion_es"] - a["inclusion_es"]) / 2)
        levels = [rev(a["inclusion"], a["accuracy"]), rev(a["inclusion"], acc_mid), rev(a["inclusion"], b["accuracy"]),
                  rev(a["inclusion"] + sp, b["accuracy"]), rev(b["inclusion"], b["accuracy"])]
        out["waterfall"] = {"start": round(levels[0]), "end": round(levels[-1]),
                            "steps": [{"id": sid, "value": round(levels[i + 1] - levels[i])}
                                      for i, sid in enumerate(["critical", "facts", "spanish", "missed"])]}
        if plan["price"]:
            out["roi"] = round(month3 / plan["price"], 1)
    return out


def export_all(db, business_id: int) -> dict:
    """Everything we hold about one business, in one file. Nothing about their customers is stored."""
    q = lambda sql: rows(db.execute(sql, (business_id,)))  # noqa: E731
    return {
        "business": load_business(db, business_id),
        "verified_facts": q("SELECT * FROM facts WHERE business_id=?"),
        "customer_questions": q("SELECT * FROM journeys WHERE business_id=?"),
        "scans": q("SELECT * FROM scans WHERE business_id=?"),
        "ai_answers": q("SELECT r.* FROM responses r JOIN scans s ON s.id=r.scan_id WHERE s.business_id=?"),
        "issues": q("SELECT * FROM incidents WHERE business_id=?"),
        "weekly_sales_totals": q("SELECT * FROM sales_weekly WHERE business_id=?"),
        "audit_log": q("SELECT * FROM audit_log WHERE business_id=?"),
    }


def run_check(req: dict) -> dict:
    """Free AI Check: what assistants say about a business before it signs up. Nothing is published."""
    seg = req["segment"]
    biz = {"id": 0, "name": req["name"], "category": req["category"], "category_es": req.get("category_es") or "",
           "segment": seg, "city": req["city"],
           "competitors": req.get("competitors") or agents.DEFAULT_COMPETITORS.get(seg, agents.DEFAULT_COMPETITORS["services"])}
    facts = [{"key": agents.standard_key(f["category"], f["label"]) or f"check.{i}", "product": "", "product_es": "", "label": f["label"],
              "label_es": f.get("label_es") or f["label"], "value": f["value"], "category": f["category"],
              "evidence": "owner", "verified_at": datetime.now(timezone.utc).isoformat()}
             for i, f in enumerate(req.get("facts") or [])]
    by_key = {f["key"]: f for f in facts}
    demo = agents.is_demo()
    out, errors = [], []
    for j in agents.check_journeys(biz, facts, req.get("services")):
        for p in agents.providers():
            try:
                if demo:
                    text, ext = agents.simulate(p, j, biz, facts, biz["competitors"], 0, set(), set())
                else:
                    text, _ = agents.ask_assistant(p, j["question"], "" if agents.is_shop(biz) else biz["city"])
                    ext = agents.extract(text, biz, facts, biz["competitors"])
            except Exception as e:
                errors.append(f"{p}: {e}")
                continue
            out.append({"provider": p, "question": j["question"], "language": j["language"],
                        "category": j["category"], "text": text, "mentioned": bool(ext["mentioned"]),
                        "competitors": ext.get("competitors", []), "claims": ext.get("claims", [])})

    def rate(rs):
        return round(100 * sum(r["mentioned"] for r in rs) / len(rs)) if rs else None

    fact_rows = []
    for f in facts:
        per = defaultdict(list)
        for r in out:
            for c in r["claims"]:
                if c.get("fact_key") == f["key"]:
                    per[r["provider"]].append(str(c["value"]))
        checks = []
        for p, vals in per.items():  # one row per assistant: its most repeated wrong value, if any
            wrong = [v for v in vals if values_match(f, v) is False]
            v = Counter(wrong or vals).most_common(1)[0][0]
            checks.append({"provider": p, "value": v, "match": values_match(f, v)})
        fact_rows.append({"label": f["label"], "category": f["category"], "value": f["value"], "said": checks,
                          "wrong": sum(1 for c in checks if c["match"] is False)})
    instead = Counter(c for r in out if not r["mentioned"] for c in r["competitors"]).most_common(3)
    unnamed = [r for r in out if not r["mentioned"] and r["competitors"]]
    return {
        "mode": "demo" if demo else "live", "errors": errors, "answers": len(out),
        "inclusion": rate(out), "inclusion_en": rate([r for r in out if r["language"] == "en"]),
        "inclusion_es": rate([r for r in out if r["language"] == "es"]),
        "by_assistant": {p: rate([r for r in out if r["provider"] == p]) for p in dict.fromkeys(r["provider"] for r in out)},
        "by_question": [{"category": c, "rate": rate([r for r in out if r["category"] == c]),
                         "answers": sum(1 for r in out if r["category"] == c),
                         "named_instead": [n for n, _ in Counter(x for r in out if r["category"] == c and not r["mentioned"]
                                                                  for x in r["competitors"]).most_common(2)],
                         "en": rate([r for r in out if r["category"] == c and r["language"] == "en"]),
                         "es": rate([r for r in out if r["category"] == c and r["language"] == "es"])}
                        for c in dict.fromkeys(r["category"] for r in out)],
        "languages": sorted({r["language"] for r in out}),
        "named_instead": [{"name": n, "count": k} for n, k in instead],
        "missed": len(unnamed),
        "facts": fact_rows,
        "wrong_facts": sum(f["wrong"] for f in fact_rows),
        "sample": unnamed[0] if unnamed else (out[0] if out else None),
    }


def list_incidents(db, business_id: int) -> list[dict]:
    inc = rows(db.execute(
        "SELECT * FROM incidents WHERE business_id=? ORDER BY "
        "CASE status WHEN 'open' THEN 0 WHEN 'needs_review' THEN 1 WHEN 'approved' THEN 2 ELSE 3 END, "
        "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, id DESC", (business_id,)))
    for i in inc:
        i["suggested_fix"] = json.loads(i["suggested_fix"]) if i["suggested_fix"] else None
    return inc
