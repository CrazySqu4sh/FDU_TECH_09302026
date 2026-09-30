"""What works: treat the assistants as a black box and measure.

We can't see why an assistant recommends someone, but every scan asks the same questions, so we can
compare. Three views:
  trend       - how inclusion and accuracy move over scans, with the scans where fixes went live marked
  signals     - how often the business is named when a signal is present vs. absent (correlation only)
  experiments - each approved fix as a before/after test against unrelated questions
                (difference-in-differences: the change on related questions minus the change on the rest)
"""
import json
from collections import defaultdict

from . import agents
from .db import rows
from .services import _scan_metrics, load_business, load_facts

MIN_GROUP = 5  # answers needed on each side before a signal is shown


def _rate(rs, key="mentioned"):
    return round(100 * sum(r[key] for r in rs) / len(rs)) if rs else None


def insights(db, business_id: int) -> dict:
    biz = load_business(db, business_id)
    facts = {f["key"]: f for f in load_facts(db, business_id)}
    scans = rows(db.execute("SELECT * FROM scans WHERE business_id=? ORDER BY id", (business_id,)))
    if not scans:
        return {"scans": []}
    ids = [s["id"] for s in scans]
    resp = rows(db.execute(
        f"SELECT r.id, r.scan_id, r.provider, r.mentioned, j.id AS jid, j.question, j.language, j.category, "
        f"j.related_facts FROM responses r JOIN journeys j ON j.id=r.journey_id "
        f"WHERE r.scan_id IN ({','.join('?' * len(ids))})", ids))
    claims = rows(db.execute(
        f"SELECT c.fact_key, c.verdict, r.id AS rid, r.scan_id, r.provider FROM claims c JOIN responses r ON r.id=c.response_id "
        f"WHERE r.scan_id IN ({','.join('?' * len(ids))})", ids))
    srcs = defaultdict(set)
    for s in rows(db.execute(
            f"SELECT s.response_id, s.domain FROM sources s JOIN responses r ON r.id=s.response_id "
            f"WHERE r.scan_id IN ({','.join('?' * len(ids))})", ids)):
        srcs[s["response_id"]].add(agents.classify_source(s["domain"], biz)[0])
    fixes = rows(db.execute(
        "SELECT * FROM incidents WHERE business_id=? AND approved_at IS NOT NULL ORDER BY approved_at", (business_id,)))

    def went_live(inc):
        """First scan after the fix was approved."""
        after = inc.get("approved_after_scan")
        for s in scans:
            if (after is not None and s["id"] > after) or (after is None and s["created_at"] > inc["approved_at"]):
                return s["id"]
        return None

    def fix_label(inc):
        if inc["type"] == "missed_opportunity":
            return f"{inc['category']} ({inc['language'].upper()})"
        f = facts.get(inc["fact_key"])
        return (f"{f['product']} · " if f and f.get("product") else "") + (f["label"] if f else inc["fact_key"])

    live = defaultdict(list)
    for inc in fixes:
        s = went_live(inc)
        if s:
            live[s].append(fix_label(inc))

    # 1. Trend
    trend = []
    for i, s in enumerate(scans):
        m = _scan_metrics(db, s["id"], list(facts.values()))
        trend.append({"scan": i, "id": s["id"], "created_at": s["created_at"], "inclusion": m["inclusion_rate"],
                      "inclusion_es": m["inclusion_es"], "accuracy": m["fact_accuracy"],
                      "fixes": sorted(set(live.get(s["id"], [])))})

    # 2. Per assistant, per scan
    by_assistant = defaultdict(list)
    for s in scans:
        rs = [r for r in resp if r["scan_id"] == s["id"]]
        for p in dict.fromkeys(r["provider"] for r in resp):
            by_assistant[p].append(_rate([r for r in rs if r["provider"] == p]))

    # 3. Heatmap: customer need x scan
    needs = list(dict.fromkeys(f"{r['category']}|{r['language']}" for r in resp))
    heat = [{"need": n.split("|")[0], "language": n.split("|")[1],
             "values": [_rate([r for r in resp if r["scan_id"] == s["id"] and f"{r['category']}|{r['language']}" == n])
                        for s in scans]} for n in needs]

    # 4. Signals (recent scans, so old behavior doesn't dominate)
    recent = [r for r in resp if r["scan_id"] in ids[-6:]]
    name = biz["name"].lower()
    tests = [("language_es", lambda r: r["language"] == "es"),
             ("branded", lambda r: name in r["question"].lower())]
    kinds = sorted({k for r in recent for k in srcs.get(r["id"], ())})
    tests += [(f"source:{k}", (lambda k: lambda r: k in srcs.get(r["id"], ()))(k)) for k in kinds]
    judged = defaultdict(list)
    for c in claims:
        if c["verdict"] != "needs_review":
            judged[c["rid"]].append(c["verdict"] == "wrong")
    for r in recent:
        r["has_wrong"] = int(any(judged.get(r["id"], [])))
        r["judged"] = r["id"] in judged

    def wrong_rate(rs):  # share of answers with checked facts that got one wrong
        return _rate([r for r in rs if r["judged"]], "has_wrong")

    signals = []
    for sid, test in tests:
        yes = [r for r in recent if test(r)]
        no = [r for r in recent if not test(r)]
        if len(yes) >= MIN_GROUP and len(no) >= MIN_GROUP:
            signals.append({"id": sid, "with": _rate(yes), "without": _rate(no), "n_with": len(yes),
                            "n_without": len(no), "lift": _rate(yes) - _rate(no),
                            "wrong_with": wrong_rate(yes), "wrong_without": wrong_rate(no)})
    signals.sort(key=lambda x: -abs(x["lift"]))

    # 5. Experiments: each fix type, before vs. after, against unrelated questions
    groups = {}
    for inc in fixes:
        s = went_live(inc)
        if not s:
            continue
        key = ("missed", inc["category"], inc["language"]) if inc["type"] == "missed_opportunity" \
            else ("fact", inc["fact_key"])
        if key not in groups or s < groups[key]["scan"]:
            groups[key] = {"scan": s, "label": fix_label(inc), "type": inc["type"]}
    experiments = []
    for key, g in groups.items():
        before = [i for i in ids if i < g["scan"]][-1:]  # last scan before the fix went live
        after = [i for i in ids if i >= g["scan"]]
        if not before or not after:
            continue
        if key[0] == "missed":
            test = lambda r: r["category"] == key[1] and r["language"] == key[2]  # noqa: E731
            pool, metric, val = resp, "inclusion", "mentioned"
        else:
            test = lambda c: c["fact_key"] == key[1]  # noqa: E731
            pool = [dict(c, ok=int(c["verdict"] == "match")) for c in claims if c["verdict"] != "needs_review"]
            metric, val = "accuracy", "ok"
        pick = lambda sids, want: [x for x in pool if x["scan_id"] in sids and bool(test(x)) == want]  # noqa: E731
        tb, ta = pick(before, True), pick(after, True)
        cb, ca = pick(before, False), pick(after, False)
        if not tb or not ta or not cb or not ca:
            continue
        change = _rate(ta, val) - _rate(tb, val)
        control = _rate(ca, val) - _rate(cb, val)
        experiments.append({"label": g["label"], "type": g["type"], "metric": metric,
                            "before": _rate(tb, val), "after": _rate(ta, val), "control_change": control,
                            "lift": change - control, "n": len(tb) + len(ta), "early": len(ta) < 12})
    experiments.sort(key=lambda x: -x["lift"])
    return {"scans": trend, "by_assistant": dict(by_assistant), "heatmap": heat, "signals": signals,
            "experiments": experiments, "fixes_live": sum(len(v) for v in live.values())}
