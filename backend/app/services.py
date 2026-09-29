"""Pipeline: journeys -> ask assistants -> extract claims -> validate -> incidents -> metrics."""
import json
from collections import Counter, defaultdict
from datetime import datetime

from . import agents
from .db import log, now, row, rows
from .validator import effective_evidence, severity_for, verdict

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
    for f in facts:
        f["effective_evidence"] = effective_evidence(f)
    return facts


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
    journeys = ensure_journeys(db, biz, facts)
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
        for p in agents.providers():
            try:
                if demo:
                    text, ext = agents.simulate(p, j, biz, facts, biz["competitors"], scan_round,
                                                fixed_keys, fixed_missed)
                else:
                    city = biz["city"] if biz.get("segment") != "ecommerce" else ""
                    text = agents.ask_assistant(p, j["question"], city)
                    ext = agents.extract(text, biz, facts, biz["competitors"])
            except Exception as e:  # one failed call shouldn't sink the scan
                errors.append(f"{p}: {e}")
                continue
            rid = db.execute(
                "INSERT INTO responses (scan_id, journey_id, provider, text, mentioned, position, competitors) "
                "VALUES (?,?,?,?,?,?,?)",
                (scan_id, j["id"], p, text, int(ext["mentioned"]), ext.get("position"),
                 json.dumps(ext.get("competitors", [])))).lastrowid
            for c in ext.get("claims", []):
                fact = by_key.get(c.get("fact_key"))
                if fact and c.get("value") not in (None, ""):
                    db.execute("INSERT INTO claims (response_id, fact_key, value, verdict) VALUES (?,?,?,?)",
                               (rid, fact["key"], str(c["value"]), verdict(fact, str(c["value"]))))

    _update_incidents(db, biz, by_key, scan_id)
    log(db, business_id, "scan_completed", "system", {"scan_id": scan_id, "mode": "demo" if demo else "live",
                                                      "errors": errors})
    return {"scan_id": scan_id, "mode": "demo" if demo else "live", "errors": errors}


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
    out = {"business": biz, "facts": facts, "scans": [], "latest": None, "matrix": [],
           "providers": agents.providers(), "mode": "demo" if agents.is_demo() else "live",
           "incidents": incidents,
           "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None}
    for s in scans:
        m = _scan_metrics(db, s["id"], facts)
        out["scans"].append({"id": s["id"], "created_at": s["created_at"], "mode": s["mode"],
                             "inclusion_rate": m["inclusion_rate"], "fact_accuracy": m["fact_accuracy"],
                             "inclusion_es": m["inclusion_es"]})
    if not scans:
        return out
    last = scans[-1]["id"]
    out["latest"] = _scan_metrics(db, last, facts)

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
                              "assistants": seen.get(f["key"], {})})
    return out


def list_incidents(db, business_id: int) -> list[dict]:
    inc = rows(db.execute(
        "SELECT * FROM incidents WHERE business_id=? ORDER BY "
        "CASE status WHEN 'open' THEN 0 WHEN 'needs_review' THEN 1 WHEN 'approved' THEN 2 ELSE 3 END, "
        "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, id DESC", (business_id,)))
    for i in inc:
        i["suggested_fix"] = json.loads(i["suggested_fix"]) if i["suggested_fix"] else None
    return inc
