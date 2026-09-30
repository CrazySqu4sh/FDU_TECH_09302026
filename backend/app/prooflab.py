"""Proof Lab: a controlled before/after test of Aparece's fixes.

Assistants answer local questions by reading a handful of search results and summarizing them. The lab
recreates that step with everything else held constant: the same four competitor pages, the same customer
questions (EN + ES), the same number of repeats. Only the business's own page changes:

  before - a typical small-business page: vague, an outdated price, no insurance or area, no Spanish
  after  - the page with Aparece's fixes: every verified fact stated plainly, plus a Spanish Q&A

Live mode (API key set) asks a real model; answers are read by code (reader.read_answer) and checked with
the same rules as real scans. Demo mode simulates answers and says so. What this does NOT show: whether a
search engine picks up the new page. Weekly real-world scans measure that part.
"""
import json

from . import agents, reader
from .db import now, row
from .validator import verdict

VERSIONS = ("before", "after")


def _rng(*parts):
    return agents._rng("lab", *parts)


def pages(biz: dict, facts: list[dict], version: str) -> dict:
    """name -> page text, as a search result would show it."""
    r = _rng(biz["name"], "competitors")
    city, cat = biz["city"], biz["category"]
    out = {}
    for c in biz["competitors"][:4]:
        lines = [f"{c} · {cat} in {city}", f"Rated {r.choice([4.2, 4.4, 4.6, 4.7])} stars ({r.randint(40, 300)} reviews)."]
        for f in facts:
            if f["category"] == "price":
                try:
                    lines.append(f"{f['label']}: ${float(f['value']) * r.uniform(0.85, 1.2):.0f}")
                except ValueError:
                    pass
        lines.append(r.choice(["Serving the whole metro area.", "Book online in minutes.", "Family-owned since 2012."]))
        out[c] = "\n".join(lines)
    by = {f["key"]: f for f in facts}
    if version == "before":
        lines = [f"{biz['name']}", f"We clean homes in {city}! Quality service at great prices. Call us today."]
        price = next((f for f in facts if f["category"] == "price"), None)
        if price:
            lines.append(f"{price['label']}: ${float(agents._distort(price) or price['value']):.0f} (2021 prices)")
        phone = next((f for f in facts if f["category"] == "contact"), None)
        if phone:
            lines.append(f"Phone: {phone['value']}")
    else:
        lines = [f"{biz['name']} · {cat} in {city}"]
        for f in facts:
            v = agents.display_value(f, f["value"])
            if f["category"] in {"service", "language"}:
                if f["value"] == "yes":
                    lines.append(f"✓ {f['label']}")
            elif f["category"] == "insurance":
                lines.append("Bonded and insured" if f["value"] == "yes" else "")
            elif f["category"] == "hours":
                lines.append(f"{f['key'].split('.')[-1].title()}: {f['value'].replace('-', ' - ')}")
            else:
                lines.append(f"{f['label']}: {v}")
        lines.append("Preguntas frecuentes (en español):")
        for f in facts:
            if f["category"] == "price":
                lines.append(f"¿Cuánto cuesta {(f.get('label_es') or f['label']).lower()}? ${float(f['value']):.0f}.")
            elif f["category"] == "service_area":
                lines.append(f"¿Dónde dan servicio? {f['value']}.")
            elif f["category"] == "insurance" and f["value"] == "yes":
                lines.append("¿Tienen seguro? Sí, con fianza y seguro.")
            elif f["category"] == "language" and f["value"] == "yes":
                lines.append("¿Hablan español? Sí, todo nuestro equipo habla español.")
        if by.get("contact.phone"):
            lines.append(json.dumps({"@type": "LocalBusiness", "name": biz["name"], "telephone": by["contact.phone"]["value"]}))
    out[biz["name"]] = "\n".join(x for x in lines if x)
    return out


def _simulate(biz, facts, page_set, version, q, rep):
    """Demo stand-in for a model reading the five pages. Probabilities reflect page quality, not a real run."""
    r = _rng(biz["name"], version, q["question"], rep)
    es = q["language"] == "es"
    p = {"before": 0.28 if not es else 0.12, "after": 0.72 if not es else 0.62}[version]
    names = list(page_set)
    r.shuffle(names)
    picked = [n for n in names if n != biz["name"]][:3]
    if r.random() < p:
        picked.insert(r.randint(0, 2), biz["name"])
        picked = picked[:3]
    lines = []
    for i, n in enumerate(picked, 1):
        if n == biz["name"]:
            page = page_set[n]
            # Repeat what the page says about the facts this question is about (so 'before' repeats the old price)
            related = [f for f in facts if f["key"] in q.get("related_facts", [])] or facts[:1]
            bits = []
            for f in related[:2]:
                c = reader.candidates(page, f, anywhere=False)
                if c:
                    bits.append(f"{f['label'].lower()} {'$' if f['category'] == 'price' else ''}{c[0][0]}")
            detail = ", ".join(bits) or ("buena opción" if es else "a solid option")
        else:
            detail = "buenas reseñas" if es else "well reviewed"
        lines.append(f"{i}. {n}: {detail}.")
    return "\n".join(lines)


def _live(biz, page_set, q, rep):
    names = list(page_set)
    _rng(biz["name"], q["question"], rep).shuffle(names)  # order changes each repeat so position doesn't decide
    results = "\n\n".join(f"[Result {i}] {n}\n{page_set[n]}" for i, n in enumerate(names, 1))
    prompt = (f"You are an AI assistant helping a customer in {biz['city']}. Use ONLY these search results.\n\n{results}\n\n"
              f"Customer question: {q['question']}\n\nRecommend up to 3 businesses as a numbered list, one line each, "
              f"with the facts from the results that matter for this question. Answer in "
              f"{'Spanish' if q['language'] == 'es' else 'English'}.")
    return agents._utility(prompt)


def run(db, business_id: int, repeats: int = 3) -> dict:
    from .services import ensure_journeys, load_business, load_facts
    biz, facts = load_business(db, business_id), load_facts(db, business_id)
    by_key = {f["key"]: f for f in facts}
    questions = ensure_journeys(db, biz, facts)[:10]
    demo = agents.is_demo()
    answers, summary = [], {}
    for version in VERSIONS:
        page_set = pages(biz, facts, version)
        for q in questions:
            for rep in range(repeats):
                text = _simulate(biz, facts, page_set, version, q, rep) if demo else _live(biz, page_set, q, rep)
                ext = reader.read_answer(text, biz, facts, biz["competitors"])
                checked = [{"fact": c["fact_key"], "value": c["value"], "verdict": verdict(by_key[c["fact_key"]], str(c["value"]))}
                           for c in ext["claims"] if c["fact_key"] in by_key]
                answers.append({"version": version, "question": q["question"], "language": q["language"],
                                "repeat": rep + 1, "named": ext["mentioned"], "position": ext["position"],
                                "claims": checked, "answer": text})
        va = [a for a in answers if a["version"] == version]
        rate = lambda xs: round(100 * sum(a["named"] for a in xs) / len(xs)) if xs else None  # noqa: E731
        judged = [c for a in va for c in a["claims"] if c["verdict"] != "needs_review"]
        summary[version] = {
            "recommended": rate(va), "recommended_en": rate([a for a in va if a["language"] == "en"]),
            "recommended_es": rate([a for a in va if a["language"] == "es"]),
            "facts_correct": round(100 * sum(c["verdict"] == "match" for c in judged) / len(judged)) if judged else None,
            "wrong_facts": sum(c["verdict"] == "wrong" for c in judged), "answers": len(va),
        }
    per_q = []
    for q in questions:
        row_ = {"question": q["question"], "language": q["language"]}
        for v in VERSIONS:
            xs = [a for a in answers if a["version"] == v and a["question"] == q["question"]]
            row_[v] = round(100 * sum(a["named"] for a in xs) / len(xs)) if xs else None
        per_q.append(row_)
    result = {"mode": "demo" if demo else "live", "model": "simulated" if demo else agents.CLAUDE_UTILITY_MODEL
              if agents.ANTHROPIC_KEY else agents.OPENAI_MODEL, "repeats": repeats, "questions": len(questions),
              "summary": summary, "per_question": per_q, "answers": answers,
              "pages": {v: pages(biz, facts, v)[biz["name"]] for v in VERSIONS}}
    rid = db.execute("INSERT INTO proof_runs (business_id, mode, created_at, results) VALUES (?,?,?,?)",
                     (business_id, result["mode"], now(), json.dumps(result, ensure_ascii=False))).lastrowid
    return {"id": rid, "created_at": now(), **result}


def latest(db, business_id: int) -> dict | None:
    r = row(db.execute("SELECT * FROM proof_runs WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    return {"id": r["id"], "created_at": r["created_at"], **json.loads(r["results"])} if r else None


def csv_text(run_: dict) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["version", "question", "language", "repeat", "named", "position", "claims", "wrong_claims", "answer"])
    for a in run_["answers"]:
        w.writerow([a["version"], a["question"], a["language"], a["repeat"], int(a["named"]), a["position"] or "",
                    "; ".join(f"{c['fact']}={c['value']} ({c['verdict']})" for c in a["claims"]),
                    sum(c["verdict"] == "wrong" for c in a["claims"]), a["answer"].replace("\n", " | ")])
    return buf.getvalue()
