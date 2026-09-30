"""Sales impact: weekly visits and revenue that AI assistants send to the business.

Live: import weekly rows from Shopify / GA4 / Square, counting sessions whose referrer is an assistant
(chatgpt.com, perplexity.ai, gemini.google.com, claude.ai, copilot.microsoft.com).
Demo: simulated from scan results so the story is visible end to end: search traffic slowly falls,
AI-referred traffic grows, and fact accuracy and inclusion decide how much of it turns into sales.
Every simulated row is stored with source='simulated' and labeled that way in the UI.

Lift is measured against a counterfactual, not against earlier weeks: AI traffic grows on its own,
so "expected_revenue" is what the same week would have earned at the inclusion and accuracy
measured on the first scan (before any fix was approved).
"""
from . import agents
from .db import row, rows

HISTORY_WEEKS = 8
# Grounded in published trends (listed with sources on the Growth plan page):
# Adobe Analytics measured AI referrals to U.S. retail sites up 693% year over year (2025 holidays), about 8x a year,
# which is ~4% a week. Gartner predicted traditional search volume down 25% by 2026 (~2 years), ~0.5% a week.
SEARCH_TREND = 0.995  # weekly change in visits from search
AI_TREND = 1.04       # weekly change in shoppers asking AI assistants in this category
DEFAULT_BASELINE = {"inclusion": 40, "accuracy": 60}  # until the first scan measures the real one
# search visits/week, AI-referred visits/week at start, conversion of AI visits, average order value
PROFILES = {
    "ecommerce": {"search": 1400, "ai": 90, "conv": 0.05, "aov": 96},
    "tech": {"search": 2600, "ai": 190, "conv": 0.04, "aov": 365},
    "services": {"search": 520, "ai": 30, "conv": 0.09, "aov": 180},
    "cleaning": {"search": 520, "ai": 40, "conv": 0.08, "aov": 180},  # a booking; average clean
    "trades": {"search": 640, "ai": 18, "conv": 0.06, "aov": 2400},  # a lead becomes a job; average job value
}


def _week(biz: dict, week: int, inclusion: float, accuracy: float, phase: str, baseline: dict) -> dict:
    p = PROFILES.get(biz.get("segment"), PROFILES["services"])
    r = agents._rng("sales", biz["id"], week)
    n1, n2, n3 = (0.94 + 0.12 * r.random() for _ in range(3))
    demand = p["ai"] * AI_TREND ** week * n1  # shoppers asking AI about this category

    def revenue(inc, acc):
        sessions = demand * (0.3 + inc / 100)
        # Wrong prices, specs or stock send shoppers away or into returns, so accuracy drives conversion.
        return sessions, sessions * p["conv"] * (0.35 + 0.65 * acc / 100) * p["aov"] * n2

    sessions, rev = revenue(inclusion, accuracy)
    _, expected = revenue(baseline["inclusion"], baseline["accuracy"])
    _, perfect = revenue(inclusion, 100)
    return {"week": week, "phase": phase,
            "search_sessions": round(p["search"] * SEARCH_TREND ** week * n3),
            "ai_sessions": round(sessions), "ai_orders": round(rev / p["aov"] / n2),
            "ai_revenue": round(rev, 2), "expected_revenue": round(expected, 2),
            "lost_revenue": round(perfect - rev, 2),
            "misinfo_contacts": round(sessions * (1 - accuracy / 100) * 0.05),
            "inclusion": round(inclusion), "accuracy": round(accuracy), "source": "simulated"}


def project(biz: dict, start_week: int, weeks: int, a: dict, b: dict, ramp: int) -> list[dict]:
    """Model estimate of AI-referred revenue: staying at point A vs. moving to point B over `ramp` weeks."""
    out = []
    for i in range(1, weeks + 1):
        f = min(i / ramp, 1)
        inc = a["inclusion"] + (b["inclusion"] - a["inclusion"]) * f
        acc = a["accuracy"] + (b["accuracy"] - a["accuracy"]) * f
        week = start_week + i
        stay = _week(biz, week, a["inclusion"], a["accuracy"], "after", a)
        plan = _week(biz, week, inc, acc, "after", a)
        out.append({"week": week, "stay": stay["ai_revenue"], "plan": plan["ai_revenue"]})
    return out


def revenue_at(biz: dict, week: int, inclusion: float, accuracy: float) -> float:
    """Model estimate of weekly AI-referred revenue at a given week and set of AI results."""
    base = {"inclusion": inclusion, "accuracy": accuracy}
    return _week(biz, week, inclusion, accuracy, "after", base)["ai_revenue"]


def _insert(db, bid: int, w: dict):
    cols = ("week", "phase", "search_sessions", "ai_sessions", "ai_orders", "ai_revenue", "expected_revenue",
            "lost_revenue", "misinfo_contacts", "inclusion", "accuracy", "source")
    db.execute(f"INSERT OR REPLACE INTO sales_weekly (business_id, {', '.join(cols)}) "
               f"VALUES (?{', ?' * len(cols)})", (bid, *(w.get(c) for c in cols)))


def _history(db, biz: dict, baseline: dict):
    for week in range(HISTORY_WEEKS):
        _insert(db, biz["id"], _week(biz, week, baseline["inclusion"], baseline["accuracy"], "before", baseline))


def ensure_history(db, biz: dict):
    """Demo only: weeks before monitoring started."""
    if not agents.is_demo() or db.execute("SELECT 1 FROM sales_weekly WHERE business_id=?", (biz["id"],)).fetchone():
        return
    _history(db, biz, DEFAULT_BASELINE)


def record_scan_week(db, biz: dict, metrics: dict):
    """Demo only: each scan stands for one more week of sales under the current AI results."""
    if not agents.is_demo():
        return
    bid = biz["id"]
    now = {"inclusion": metrics.get("inclusion_rate") or DEFAULT_BASELINE["inclusion"],
           "accuracy": metrics.get("fact_accuracy") or DEFAULT_BASELINE["accuracy"]}
    first = row(db.execute("SELECT inclusion, accuracy FROM sales_weekly WHERE business_id=? AND phase='after' "
                           "ORDER BY week LIMIT 1", (bid,)))
    if first is None:
        # The first scan shows how AI described the business before monitoring: that's the baseline.
        if db.execute("SELECT 1 FROM sales_weekly WHERE business_id=? AND source='imported'", (bid,)).fetchone():
            return
        _history(db, biz, now)
        baseline = now
    else:
        baseline = first
    last = db.execute("SELECT MAX(week) FROM sales_weekly WHERE business_id=?", (bid,)).fetchone()[0]
    _insert(db, bid, _week(biz, (last or 0) + 1 if last is not None else HISTORY_WEEKS,
                           now["inclusion"], now["accuracy"], "after", baseline))


def import_weeks(db, bid: int, weeks: list[dict]):
    """Live: replace the series with real weekly numbers (from a store or analytics export)."""
    db.execute("DELETE FROM sales_weekly WHERE business_id=?", (bid,))
    for i, w in enumerate(weeks):
        _insert(db, bid, {"week": i, **w, "source": "imported"})


def _pct(new, old):
    return round(100 * (new - old) / old) if old else None


def summary(db, bid: int) -> dict | None:
    weeks = rows(db.execute("SELECT * FROM sales_weekly WHERE business_id=? ORDER BY week", (bid,)))
    if not weeks:
        return None
    first, last = weeks[0], weeks[-1]
    after = [w for w in weeks if w["phase"] == "after"]
    fixed = after[1:]  # the first monitored week is the measurement, before any fix
    share = lambda w: round(100 * w["ai_sessions"] / ((w["ai_sessions"] + w["search_sessions"]) or 1))  # noqa: E731
    expected = sum(w["expected_revenue"] or 0 for w in fixed)
    actual = sum(w["ai_revenue"] for w in fixed)
    return {
        "weeks": weeks,
        "source": last["source"],
        "ai_share_now": share(last), "ai_share_start": share(first), "weeks_span": len(weeks) - 1,
        "search_change": _pct(last["search_sessions"], first["search_sessions"]),
        "ai_change": _pct(last["ai_sessions"], first["ai_sessions"]),
        "ai_revenue_last": last["ai_revenue"],
        "lost_revenue_last": last["lost_revenue"],
        "misinfo_contacts_last": last["misinfo_contacts"],
        "misinfo_contacts_start": after[0]["misinfo_contacts"] if after else None,
        "extra_revenue": round(actual - expected) if fixed and expected else None,
        "revenue_lift": _pct(actual, expected) if fixed and expected else None,
        "monitoring_week": after[0]["week"] if after else None,
    }
