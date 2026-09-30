"""Plans. The server enforces every limit here; the UI only shows what is locked and why.

Governance is never a paid extra: the human approval gate, evidence levels and the audit log
are in every plan, including the free trial.
"""
TRIAL_DAYS = 14
GUARANTEE = {"accuracy": 90, "days": 60}  # Gold: reach 90% fact accuracy within 60 days or next month is free

# Feature keys, in the order the pricing table lists them.
FEATURES = [
    "truth_vs_ai", "bilingual", "approval_gate", "audit_log",
    "missed_opportunities", "scan_history", "sales_basic", "unlimited_fixes",
    "product_accuracy", "sales_full", "guarantee",
    "multi_brand", "api_access", "custom_languages", "sso",
]

PLANS = {
    "trial": {
        "price": 0, "assistants": 2, "journeys": 6, "fix_drafts": 3, "scan_frequency": "weekly",
        "features": ["truth_vs_ai", "bilingual", "approval_gate", "audit_log"],
    },
    "silver": {
        "price": 29, "assistants": 3, "journeys": 12, "fix_drafts": None, "scan_frequency": "weekly",
        "features": ["truth_vs_ai", "bilingual", "approval_gate", "audit_log", "missed_opportunities",
                     "scan_history", "sales_basic", "unlimited_fixes"],
    },
    "gold": {
        "price": 99, "assistants": None, "journeys": 24, "fix_drafts": None, "scan_frequency": "daily",
        "features": ["truth_vs_ai", "bilingual", "approval_gate", "audit_log", "missed_opportunities",
                     "scan_history", "sales_basic", "unlimited_fixes", "product_accuracy", "sales_full",
                     "guarantee"],
    },
    "enterprise": {
        "price": None, "assistants": None, "journeys": 48, "fix_drafts": None, "scan_frequency": "daily",
        "features": FEATURES,
    },
}
# Community pricing: certified Hispanic- or minority-owned businesses (chamber, SBA 8(a), NMSDC, or a
# partner nonprofit) get Silver at this price, and partners can sponsor seats.
COMMUNITY_SILVER_PRICE = 15


def get(plan_id: str) -> dict:
    return {"id": plan_id if plan_id in PLANS else "trial", **PLANS.get(plan_id, PLANS["trial"])}


def has(plan_id: str, feature: str) -> bool:
    return feature in get(plan_id)["features"]


def catalog() -> dict:
    return {"plans": [{"id": k, **v} for k, v in PLANS.items()], "features": FEATURES,
            "community_silver_price": COMMUNITY_SILVER_PRICE, "trial_days": TRIAL_DAYS, "guarantee": GUARANTEE}
