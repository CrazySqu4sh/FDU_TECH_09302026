"""Deterministic checks. AI extracts claims; plain code decides if they're right.

Evidence levels (strongest first):
  system   - synced from POS / online store (never expires while connected)
  document - backed by an uploaded document or public record
  owner    - typed or approved by the owner
  expired  - an owner/document fact past its refresh window

Fact categories: hours, price, service, language, contact, policy (services)
                 stock, shipping, returns (e-commerce; price is shared)
                 spec, feature, warranty (tech products)
                 license, insurance, service_area (trades and contractors)
Only facts at 'document' or 'system' can mark an AI answer as definitely wrong.
Weaker facts produce 'needs_review' so a person checks before anyone acts.
"""
import re
from datetime import datetime, timezone, timedelta

# 'confirmed' = owner-entered but found matching on 2+ independent pages (see evidence.verify_facts)
EVIDENCE_RANK = {"expired": 0, "owner": 1, "confirmed": 2, "document": 2, "system": 3}
REFRESH_DAYS = {"stock": 7, "price": 30, "shipping": 60, "hours": 90}  # everything else: 180
SEVERITY = {"contact": "critical", "price": "high", "hours": "high", "stock": "high", "returns": "high",
            "shipping": "medium", "spec": "high", "feature": "high", "warranty": "high",
            "license": "critical", "insurance": "critical", "service_area": "medium"}


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


def _norm_spec(v: str):
    """'16 GB RAM' -> (16.0, 'gb'); '1 TB' -> (1024.0, 'gb'); '90%' -> (90.0, '%')."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(tb|gb|mb|mah|hz|in|inch|\"|%|w)?", v.strip().lower())
    if not m:
        return None
    n, unit = float(m.group(1)), (m.group(2) or "").replace("inch", "in").replace('"', "in")
    if unit == "tb":
        n, unit = n * 1024, "gb"
    return (n, unit)


def _norm_months(v: str):
    """'12' / '12 months' / '1 year' / '90 days' -> months. 'none' -> 0."""
    v = v.strip().lower()
    if v in {"none", "no warranty", "sin garantía", "sin garantia", "as is"}:
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*(day|día|dia|week|semana|month|mes|year|año|ano)?", v)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2) or "month"
    factor = {"day": 1 / 30, "día": 1 / 30, "dia": 1 / 30, "week": 0.25, "semana": 0.25,
              "year": 12, "año": 12, "ano": 12}.get(unit, 1)
    return round(n * factor, 1)


NO_LICENSE = {"none", "no", "unlicensed", "not licensed", "sin licencia", "no license"}


def _norm_license(v: str):
    v = v.strip().lower()
    if v in NO_LICENSE:
        return ""
    return re.sub(r"[^a-z0-9]", "", v)


def _norm_cities(v: str) -> set:
    return {c.strip().lower() for c in re.split(r",|;|/| and | y ", v) if c.strip()}


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
    if cat in {"service", "language", "feature", "insurance"}:
        a, b = _norm_bool(truth), _norm_bool(claimed)
        return None if b is None else a == b
    if cat == "stock":
        a, b = _norm_stock(truth), _norm_stock(claimed)
        return None if b is None else a == b
    if cat in {"shipping", "returns"}:
        a, b = _norm_days(truth), _norm_days(claimed)
        return None if a is None or b is None else a == b
    if cat == "spec":
        a, b = _norm_spec(truth), _norm_spec(claimed)
        if a is None or b is None:
            return None
        return a[0] == b[0] and (not a[1] or not b[1] or a[1] == b[1])
    if cat == "license":
        a, b = _norm_license(truth), _norm_license(claimed)
        if not b:  # "not licensed" is a claim we can judge
            return not a
        return a == b or (a.endswith(b) or b.endswith(a)) and min(len(a), len(b)) >= 4
    if cat == "service_area":
        # Wrong only if AI says they serve somewhere they don't. Naming fewer cities isn't an error.
        return _norm_cities(claimed) <= _norm_cities(truth)
    if cat == "warranty":
        a, b = _norm_months(truth), _norm_months(claimed)
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
    level = fact.get("effective_evidence") or effective_evidence(fact)
    strong = EVIDENCE_RANK[level] >= EVIDENCE_RANK["document"]
    return "wrong" if strong else "needs_review"
