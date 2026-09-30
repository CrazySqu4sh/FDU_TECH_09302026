"""Evidence: the proof behind every finding.

1. verify_facts      - read the business's own website and the listings that mention it, record what each
                       one says for every verified fact, and flag listings that disagree (a common root cause).
2. check_citations   - for a wrong AI claim, open the pages the assistant cited and decide:
                       copied (a cited page says the same wrong thing), made_up (no cited page says it),
                       or unclear (pages couldn't be read, or nothing was cited).
3. report            - one exportable record per finding: the truth and who confirms it, the exact AI answers
                       with time and model, the cited pages with fingerprints (SHA-256), and the approval trail.

Every page we read is saved as a snapshot with a SHA-256 fingerprint, so anyone can check it wasn't changed.
Demo businesses use '.example' domains, so their pages are simulated and stored with simulated=1.
"""
import hashlib
import json
import urllib.request
from collections import defaultdict

from . import agents, reader
from .db import log, now, row, rows
from .validator import severity_for, values_match

UA = "Mozilla/5.0 (compatible; AapareceVerifier/1.0; fact-checking for the business owner)"
MAX_BYTES = 1_500_000


# ------------------------------------------------------------ pages

def _demo_page(domain: str, biz: dict, facts: list[dict], stale: bool) -> str:
    """Believable listing text for demo domains. The stale directory holds the old, wrong values."""
    by = {f["category"]: f for f in facts}
    val = lambda f: (agents._distort(f) or f["value"]) if stale else f["value"]  # noqa: E731
    lines = [f"{biz['name']} · {biz['category']} · {biz['city']}"]
    own = agents.domain_of(biz.get("website") or "")
    if stale:
        lines.append("Listing last updated 2019")
    for f in facts:
        cat = f["category"]
        if cat == "contact":
            lines.append(f"Phone: {val(f)}")
        elif cat == "price" and (domain in (own,) or stale or any(x in domain for x in ("thumbtack", "angi", "yelp"))):
            lines.append(f"{f['label']}: ${float(val(f)):.0f}" if val(f).replace('.', '', 1).isdigit() else f"{f['label']}: {val(f)}")
        elif cat == "hours" and (domain == own or stale or "google" in domain):
            day = f["key"].split(".")[-1].title()
            v = val(f)
            lines.append(f"{day}: {'Closed' if v == 'closed' else v.replace('-', ' - ')}")
        elif cat == "insurance" and (domain == own or stale or "angi" in domain or "thumbtack" in domain):
            lines.append("Not insured" if val(f) == "no" else "Bonded and insured")
        elif cat in {"service", "language"} and domain == own and f["value"] == "yes":
            lines.append(f"{f['label']} · {f.get('label_es') or ''}")
        elif cat == "service_area" and domain == own:
            lines.append(f"Service area: {f['value']}")
    if domain == own and "contact" in by:
        lines.append(json.dumps({"@context": "https://schema.org", "@type": "LocalBusiness", "name": biz["name"],
                                 "telephone": by["contact"]["value"]}))
    return "\n".join(lines)


def snapshot(db, url: str, biz: dict, facts: list[dict]) -> dict:
    """Fetch (or simulate) a page and store it with a fingerprint. Reuses a snapshot from the last hour."""
    domain = agents.domain_of(url)
    recent = row(db.execute("SELECT * FROM page_snapshots WHERE url=? AND fetched_at > datetime('now','-1 hour') "
                            "ORDER BY id DESC LIMIT 1", (url,)))
    if recent:
        return recent
    simulated = agents.is_demo() or domain.endswith(".example")
    if simulated:
        stale_url = agents.DEMO_STALE.get(biz.get("segment"), "")
        text, status = _demo_page(domain, biz, facts, stale=bool(stale_url) and stale_url in url), "simulated"
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read(MAX_BYTES).decode(resp.headers.get_content_charset() or "utf-8", "replace")
            text, blocks = reader.html_to_text(raw)
            if blocks:
                text += "\n" + json.dumps(blocks)
            status = "ok"
        except Exception as e:  # blocked, timeout, not found: recorded, never guessed
            text, status = "", f"error: {type(e).__name__}"
    sha = hashlib.sha256(text.encode()).hexdigest()
    sid = db.execute("INSERT INTO page_snapshots (url, domain, fetched_at, sha256, status, text, simulated) "
                     "VALUES (?,?,?,?,?,?,?)", (url, domain, now(), sha, status, text[:200_000], int(simulated))).lastrowid
    return row(db.execute("SELECT * FROM page_snapshots WHERE id=?", (sid,)))


def _blocks(text: str) -> list:
    out = []
    for line in text.splitlines():
        if line.startswith("{") or line.startswith("["):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


# ------------------------------------------------------------ 1. confirm facts

def listing_urls(db, biz: dict) -> list[str]:
    """Pages to check: the business's website plus the pages assistants actually cite for it."""
    urls = [biz["website"]] if biz.get("website") else []
    if agents.is_demo() or (biz.get("website") or "").endswith(".example"):
        seg = biz.get("segment") if biz.get("segment") in agents.DEMO_SOURCES else "services"
        urls += [f"https://{d}" for d in agents.DEMO_SOURCES[seg][:4]] + [f"https://{agents.DEMO_STALE[seg]}"]
    else:
        cited = rows(db.execute(
            "SELECT s.url, COUNT(*) n FROM sources s JOIN responses r ON r.id=s.response_id JOIN scans c ON c.id=r.scan_id "
            "WHERE c.business_id=? AND r.mentioned=1 GROUP BY s.url ORDER BY n DESC LIMIT 6", (biz["id"],)))
        urls += [c["url"] for c in cited]
    return list(dict.fromkeys(urls))


def verify_facts(db, business_id: int, facts: list[dict], biz: dict) -> dict:
    db.execute("DELETE FROM evidence WHERE business_id=?", (business_id,))
    pages = [snapshot(db, u, biz, facts) for u in listing_urls(db, biz)]
    conflicts = 0
    for p in pages:
        if p["status"] not in ("ok", "simulated"):
            continue
        blocks = _blocks(p["text"])
        for f in facts:
            value, snip = reader.found_on_page(p["text"], blocks, f)
            if value is None:
                continue
            agrees = values_match(f, value)
            db.execute("INSERT INTO evidence (business_id, fact_key, snapshot_id, domain, url, value_found, agrees, "
                       "snippet, checked_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (business_id, f["key"], p["id"], p["domain"], p["url"], str(value),
                        None if agrees is None else int(agrees), snip[:240], now()))
            if agrees is False:
                conflicts += _conflict_incident(db, biz, f, p, value)
    log(db, business_id, "facts_verified", "system", {"pages": len(pages), "conflicts": conflicts})
    return {"pages": len(pages), "conflicts": conflicts}


def _conflict_incident(db, biz, fact, page, value) -> int:
    """A listing that disagrees with the truth is its own issue: AI reads it and repeats it."""
    exists = row(db.execute(
        "SELECT id FROM incidents WHERE business_id=? AND type='source_conflict' AND fact_key=? AND provider=? "
        "AND status IN ('open','needs_review','approved')", (biz["id"], fact["key"], page["domain"])))
    if exists:
        return 0
    db.execute(
        "INSERT INTO incidents (business_id, type, fact_key, provider, ai_value, verified_value, detail, severity, "
        "status, created_at, origin_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (biz["id"], "source_conflict", fact["key"], page["domain"], str(value), fact["value"],
         f"{page['domain']} shows “{value}”", severity_for(fact), "open", now(), page["url"]))
    return 1


def fact_confirmations(db, business_id: int) -> dict:
    """fact_key -> {'agree': [domains], 'disagree': [{domain, value}]}"""
    out = defaultdict(lambda: {"agree": [], "disagree": []})
    for e in rows(db.execute("SELECT * FROM evidence WHERE business_id=?", (business_id,))):
        if e["agrees"] == 1:
            out[e["fact_key"]]["agree"].append(e["domain"])
        elif e["agrees"] == 0:
            out[e["fact_key"]]["disagree"].append({"domain": e["domain"], "value": e["value_found"]})
    return {k: {"agree": sorted(set(v["agree"])), "disagree": v["disagree"]} for k, v in out.items()}


# ------------------------------------------------------------ 2. copied or made up?

def check_citations(db, incident_id: int) -> dict:
    inc = row(db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)))
    if not inc or inc["type"] != "wrong_fact":
        return {"origin": None}
    from .services import load_business, load_facts  # avoid a circular import at module load
    biz = load_business(db, inc["business_id"])
    facts = load_facts(db, inc["business_id"])
    fact = next((f for f in facts if f["key"] == inc["fact_key"]), None)
    if not fact:
        return {"origin": None}
    urls = [r["url"] for r in rows(db.execute(
        "SELECT DISTINCT s.url FROM claims c JOIN responses r ON r.id=c.response_id JOIN sources s ON s.response_id=r.id "
        "JOIN scans sc ON sc.id=r.scan_id WHERE sc.business_id=? AND c.fact_key=? AND r.provider=? AND c.value=? "
        "ORDER BY sc.id DESC LIMIT 8", (inc["business_id"], inc["fact_key"], inc["provider"], inc["ai_value"])))]
    db.execute("DELETE FROM citation_checks WHERE incident_id=?", (incident_id,))
    readable, copied_from = 0, None
    for u in urls:
        p = snapshot(db, u, biz, facts)
        ok = p["status"] in ("ok", "simulated")
        readable += ok
        yes, snip = reader.supports(p["text"], fact, inc["ai_value"]) if ok else (False, "")
        db.execute("INSERT INTO citation_checks (incident_id, snapshot_id, domain, url, supports, snippet, checked_at) "
                   "VALUES (?,?,?,?,?,?,?)", (incident_id, p["id"], p["domain"], u, None if not ok else int(yes),
                                              snip[:240], now()))
        if yes and not copied_from:
            copied_from = u
    origin = "copied" if copied_from else ("made_up" if readable else "unclear")
    db.execute("UPDATE incidents SET origin=?, origin_source=? WHERE id=?", (origin, copied_from, incident_id))
    log(db, inc["business_id"], "citations_checked", "system",
        {"incident_id": incident_id, "origin": origin, "pages": len(urls)})
    return {"origin": origin, "source": copied_from, "pages": len(urls)}


# ------------------------------------------------------------ 3. evidence report

def report(db, incident_id: int) -> dict | None:
    inc = row(db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)))
    if not inc:
        return None
    from .services import load_business, load_facts
    biz = load_business(db, inc["business_id"])
    fact = next((f for f in load_facts(db, inc["business_id"]) if f["key"] == inc["fact_key"]), None)
    conf = fact_confirmations(db, inc["business_id"]).get(inc["fact_key"], {"agree": [], "disagree": []})
    ev = rows(db.execute(
        "SELECT e.domain, e.url, e.value_found, e.agrees, e.snippet, p.fetched_at, p.sha256, p.simulated "
        "FROM evidence e LEFT JOIN page_snapshots p ON p.id=e.snapshot_id WHERE e.business_id=? AND e.fact_key=?",
        (inc["business_id"], inc["fact_key"])))
    answers = []
    if inc["type"] == "wrong_fact":
        for r in rows(db.execute(
                "SELECT r.id, r.provider, r.text, r.model, j.question, j.language, s.created_at, s.mode FROM claims c "
                "JOIN responses r ON r.id=c.response_id JOIN journeys j ON j.id=r.journey_id JOIN scans s ON s.id=r.scan_id "
                "WHERE s.business_id=? AND c.fact_key=? AND r.provider=? AND c.value=? ORDER BY s.id DESC LIMIT 5",
                (inc["business_id"], inc["fact_key"], inc["provider"], inc["ai_value"]))):
            _, _, seg = reader.business_segment(r["text"], biz["name"])
            answers.append({"assistant": r["provider"], "model": r["model"] or ("simulated" if r["mode"] == "demo" else ""),
                            "asked_at": r["created_at"], "question": r["question"], "language": r["language"],
                            "scan_mode": r["mode"], "excerpt": seg.strip()[:400],
                            "sha256": hashlib.sha256(r["text"].encode()).hexdigest(),
                            "sources": [s["url"] for s in rows(db.execute("SELECT url FROM sources WHERE response_id=?", (r["id"],)))]})
    cites = rows(db.execute(
        "SELECT c.domain, c.url, c.supports, c.snippet, p.fetched_at, p.sha256, p.simulated, p.status FROM citation_checks c "
        "LEFT JOIN page_snapshots p ON p.id=c.snapshot_id WHERE c.incident_id=?", (incident_id,)))
    trail = [a for a in rows(db.execute("SELECT * FROM audit_log WHERE business_id=? ORDER BY id", (inc["business_id"],)))
             if a["detail"] and f'"incident_id": {incident_id}' in a["detail"]]
    return {
        "generated_at": now(),
        "business": {"name": biz["name"], "city": biz["city"]},
        "finding": {k: inc[k] for k in ("id", "type", "fact_key", "provider", "ai_value", "verified_value", "severity",
                                         "status", "detail", "created_at", "origin", "origin_source")},
        "truth": {"fact": fact["label"] if fact else inc["fact_key"], "value": fact["value"] if fact else None,
                  "evidence_level": fact["effective_evidence"] if fact else None, "source": fact["source"] if fact else None,
                  "confirmed_by": conf["agree"], "disagreeing_listings": conf["disagree"], "pages": ev},
        "ai_answers": answers,
        "cited_pages": cites,
        "approval_trail": [{"action": a["action"], "by": a["actor"], "at": a["at"]} for a in trail],
        "checker": checker_accuracy(db, inc["business_id"]),
    }


# ------------------------------------------------------------ checking the checker

def checker_accuracy(db, business_id: int) -> dict:
    ls = rows(db.execute(
        "SELECT l.human_verdict, c.verdict FROM labels l JOIN claims c ON c.id=l.claim_id JOIN responses r ON r.id=c.response_id "
        "JOIN scans s ON s.id=r.scan_id WHERE s.business_id=?", (business_id,)))
    norm = lambda v: "unclear" if v in ("needs_review", "unclear") else v  # noqa: E731
    agree = sum(norm(x["human_verdict"]) == norm(x["verdict"]) for x in ls)
    return {"labeled": len(ls), "agree": agree, "accuracy": round(100 * agree / len(ls)) if ls else None}
