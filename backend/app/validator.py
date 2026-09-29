"""Deterministic checks. AI extracts claims; plain code decides if they're right.

Evidence levels (strongest first):
  system   - synced from POS / online store (never expires while connected)
  document - backed by an uploaded document or public record
  owner    - typed or approved by the owner
  expired  - an owner/document fact past its refresh window

Fact categories: hours, price, service, language, contact, policy (services)
                 stock, shipping, returns (e-commerce; price is shared)
Only facts at 'document' or 'system' can mark an AI answer as definitely wrong.
Weaker facts produce 'needs_review' so a person checks before anyone acts.
"""
import re
from datetime import datetime, timezone, timedelta

EVIDENCE_RANK = {"expired": 0, "owner": 1, "document": 2, "system": 3}
REFRESH_DAYS = {"stock": 7, "price": 30, "shipping": 60, "hours": 90}  # everything else: 180
SEVERITY = {"contact": "critical", "price": "high", "hours": "high", "stock": "high", "returns": "high",
            "shipping": "medium"}


def effective_evidence(fact: dict) -> str:
    level = fact["evidence"]
    if level == "system":
        return level
    days = REFRESH_DAYS.get(fact["category"], 180)
    verified = datetime.fromisoformat(fact["verified_at"])
    if datetime.now(timezone.utc) - verified > timedelta(days=days):
        return "owner" if level == "document" else "expired"
    return level


def severity_for(fact: dict) -> str:
    return SEVERITY.get(fact["category"], "medium")


def _norm_hours(v: str):
    v = v.strip().lower()
    if v in {"closed", "cerrado"}:
        return "closed"
    times = re.findall(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", v)
    if len(times) < 2:
        return v
    out = []
    for h, m, ap in times[:2]:
        h = int(h)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        out.append(f"{h:02d}:{int(m or 0):02d}")
    return "-".join(out)


def _norm_price(v: str):
    m = re.search(r"\d+(?:[.,]\d{1,2})?", v.replace(",", ""))
    return float(m.group()) if m else None


def _norm_stock(v: str):
    v = v.strip().lower()
    if any(w in v for w in ("out of stock", "sold out", "agotado", "unavailable", "no disponible")) or v == "no":
        return False
    if any(w in v for w in ("in stock", "available", "disponible", "en existencia")) or v == "yes":
        return True
    return None


def _norm_days(v: str):
    """'3-5 days' -> (3, 5); '30' -> (30, 30); 'none'/'final sale' -> (0, 0)."""
    v = v.strip().lower()
    if v in {"none", "no returns", "final sale", "sin devoluciones"}:
        return (0, 0)
    nums = [int(n) for n in re.findall(r"\d+", v)]
    if not nums:
        return None
    return (nums[0], nums[1] if len(nums) > 1 else nums[0])


def _norm_bool(v: str):
    v = v.strip().lower()
    if v in {"yes", "true", "si", "sí", "y"}:
        return True
    if v in {"no", "false", "n"}:
        return False
    return None


def values_match(fact: dict, claimed: str) -> bool | None:
    """True/False when we can decide; None when the claim can't be parsed."""
    cat, truth = fact["category"], fact["value"]
    if cat == "hours":
        return _norm_hours(truth) == _norm_hours(claimed)
    if cat == "price":
        a, b = _norm_price(truth), _norm_price(claimed)
        if a is None or b is None:
            return None
        return abs(a - b) <= max(0.02 * a, 0.5)
    if cat in {"service", "language"}:
        a, b = _norm_bool(truth), _norm_bool(claimed)
        return None if b is None else a == b
    if cat == "stock":
        a, b = _norm_stock(truth), _norm_stock(claimed)
        return None if b is None else a == b
    if cat in {"shipping", "returns"}:
        a, b = _norm_days(truth), _norm_days(claimed)
        return None if a is None or b is None else a == b
    if cat == "contact":
        return re.sub(r"\D", "", truth)[-10:] == re.sub(r"\D", "", claimed)[-10:]
    return truth.strip().lower() == claimed.strip().lower()


def verdict(fact: dict, claimed: str) -> str:
    """match | wrong | needs_review"""
    ok = values_match(fact, claimed)
    if ok:
        return "match"
    if ok is None:
        return "needs_review"
    strong = EVIDENCE_RANK[effective_evidence(fact)] >= EVIDENCE_RANK["document"]
    return "wrong" if strong else "needs_review"
