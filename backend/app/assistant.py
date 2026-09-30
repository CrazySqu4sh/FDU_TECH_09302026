"""AI Business Assistant: answers the owner's questions from their own scan data, never from general knowledge.

Live mode sends a compact summary of the business's results to the model with strict instructions.
Demo mode (no keys) answers the common questions with templates over the same data, so the demo is honest.
"""
import json
import re
from collections import Counter

from . import agents, services
from .db import row, rows

NAMES = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini", "perplexity": "Perplexity"}
ES_HINTS = re.compile(r"[¿¡ñáéíóú]|\b(qué|que|por|cómo|como|dónde|donde|mi|mis|precio|horario|competencia|español|arreglar|primero|ventas|clientes)\b", re.I)


def context(db, business_id: int) -> dict:
    """Everything the assistant may use, kept small enough to send to a model."""
    dash = services.dashboard(db, business_id)
    biz, L = dash["business"], dash["latest"] or {}
    facts = {f["key"]: f for f in dash["facts"]}
    active = [i for i in dash["incidents"] if i["status"] in ("open", "needs_review")]

    def issue(i):
        if i["type"] == "source_conflict":
            f = facts.get(i["fact_key"], {})
            return {"type": "listing_conflict", "site": i["provider"], "fact": f.get("label", i["fact_key"]),
                    "category": f.get("category"), "listing_says": i["ai_value"], "truth": i["verified_value"]}
        if i["type"] == "missed_opportunity":
            return {"type": "missed", "question": i["category"], "language": i["language"], "detail": i["detail"]}
        f = facts.get(i["fact_key"], {})
        return {"type": "wrong_fact", "fact": f.get("label", i["fact_key"]), "fact_es": f.get("label_es") or f.get("label", i["fact_key"]),
                "category": f.get("category"),
                "assistant": NAMES.get(i["provider"], i["provider"]), "ai_says": i["ai_value"],
                "truth": i["verified_value"], "severity": i["severity"], "status": i["status"],
                "origin": i.get("origin"), "copied_from": i.get("origin_source")}

    last = row(db.execute("SELECT id FROM scans WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)))
    instead = Counter()
    if last:
        for r in rows(db.execute("SELECT competitors FROM responses WHERE scan_id=? AND mentioned=0", (last["id"],))):
            instead.update(json.loads(r["competitors"]))
    perc = services.perception(db, business_id) or {}
    growth = services.growth_plan(db, business_id) or {}
    return {
        "business": {"name": biz["name"], "type": biz["category"], "city": biz["city"], "plan": dash["plan"]["id"]},
        "latest_scan": {k: L.get(k) for k in ("inclusion_rate", "inclusion_en", "inclusion_es", "fact_accuracy",
                                               "missed_opportunities", "by_assistant")},
        "weakest_questions": (L.get("by_need") or [])[:4],
        "open_issues": [issue(i) for i in sorted(active, key=lambda i: {"critical": 0, "high": 1}.get(i["severity"], 2))][:10],
        "locked_missed_opportunities": dash.get("locked_missed", 0),
        "competitors_named_instead": [{"name": n, "answers": c} for n, c in instead.most_common(3)],
        "sources": [{k: s[k] for k in ("label", "domain", "cited", "wrong_share", "likely_cause")}
                    for s in (perc.get("sources") or [])[:6]],
        "never_mentioned": perc.get("never_mentioned", []),
        "growth": {k: growth.get(k) for k in ("extra_month3", "extra_jobs_month3", "extra_90_low", "extra_90_high", "roi")
                   } | {"steps": [{"step": s["id"], "weeks": s["weeks"], "count": s["count"], "done": s["done"]}
                                  for s in growth.get("steps", [])]},
    }


def _val(cat, v, es):
    """Owner-friendly value: 'no' insurance -> 'not insured', 135.00 -> $135."""
    v = str(v)
    yes = v.strip().lower() in {"yes", "sí", "si", "true"}
    if cat == "insurance":
        return ("con seguro" if yes else "sin seguro") if es else ("insured" if yes else "not insured")
    if cat in {"service", "language", "feature"}:
        return ("sí" if yes else "no") if es else ("yes" if yes else "no")
    if cat == "price":
        try:
            return f"${float(v):,.0f}"
        except ValueError:
            return v
    if cat in {"returns", "warranty"}:
        if v in {"none", "0"}:
            return ("sin devoluciones" if es else "no returns") if cat == "returns" else ("sin garantía" if es else "no warranty")
        return f"{v} {'días' if es else 'days'}" if cat == "returns" else f"{v} {'meses' if es else 'months'}"
    if cat == "hours" and v == "closed":
        return "cerrado" if es else "closed"
    return v


def _money(v):
    return f"${v:,.0f}" if v is not None else "–"


def _rule_answer(q: str, c: dict, es: bool) -> tuple[str, str | None]:
    """Demo answers over the same data. Returns (text, tab to open)."""
    ql = q.lower()
    L, issues = c["latest_scan"], c["open_issues"]
    seen, wrong = set(), []
    for i in issues:  # one line per assistant and fact
        if i["type"] == "wrong_fact" and (i["assistant"], i["fact"]) not in seen:
            seen.add((i["assistant"], i["fact"]))
            wrong.append(dict(i, fact=i["fact_es"]) if es else i)
    missed = [i for i in issues if i["type"] == "missed"]
    inst = c["competitors_named_instead"]
    cause = next((s for s in c["sources"] if s["likely_cause"]), None)
    g = c["growth"]
    has = lambda *w: any(x in ql for x in w)  # noqa: E731

    if has("first", "priorit", "start", "primero", "empiezo", "empezar", "should i fix", "debo arreglar"):
        if not wrong and not missed:
            return ("Nada urgente ahora. Sigue con revisiones semanales." if es else
                    "Nothing urgent right now. Keep the weekly scans going."), "overview"
        top = wrong[:2] if wrong else []
        def line(i):
            if i["category"] == "insurance":  # the most damaging claim reads best in plain words
                return (f"{i['assistant']} dice que no tienes seguro, pero sí tienes" if es else
                        f"{i['assistant']} says you're not insured, but you are")
            return (f"{i['assistant']} dice “{_val(i['category'], i['ai_says'], es)}” en tu {i['fact'].lower()} "
                    f"(verdadero: {_val(i['category'], i['truth'], es)})" if es else
                    f"{i['assistant']} says “{_val(i['category'], i['ai_says'], es)}” for your {i['fact'].lower()} "
                    f"(true: {_val(i['category'], i['truth'], es)})")
        lines = [line(i) for i in top]
        gain = (f" Si sigues el plan, calculamos unos {g['extra_jobs_month3']} trabajos más al mes para el mes 3."
                if es else f" If you follow the plan, we estimate about {g['extra_jobs_month3']} more jobs a month by month 3.") \
            if g.get("extra_jobs_month3") else ""
        head = "Empieza por lo que puede costarte clientes hoy: " if es else "Start with what can cost you customers today: "
        return head + "; ".join(lines) + "." + (f" Luego, las {len(missed)} preguntas donde nombran a otro." if es and missed else
                                                  f" Then the {len(missed)} questions where AI names someone else." if missed else "") + gain, "issues"

    if has("competitor", "competencia", "instead", "en vez", "who appears", "quién aparece", "quien aparece", "rival"):
        if not inst:
            return ("En la última revisión no nombraron a otro negocio en tu lugar." if es else
                    "In the latest scan, no other business was named in your place."), "answers"
        top = ", ".join(f"{x['name']} ({x['answers']})" for x in inst)
        return ((f"Cuando la IA no te nombra, recomienda más a: {top}. Revisa “Qué funciona” para ver qué preguntas pierdes."
                 if es else f"When AI leaves you out, it most often names: {top} (number of answers). "
                 "See which questions you lose in What works."), "works")

    if has("price", "pricing", "precio", "cost", "cuesta", "hour", "horario", "open", "abierto", "accura", "correct",
           "wrong", "incorrect", "mal", "hallucin", "insur", "seguro", "phone", "teléfono", "telefono"):
        cat = ("price" if has("price", "pricing", "precio", "cost", "cuesta") else
               "hours" if has("hour", "horario", "open", "abierto") else
               "insurance" if has("insur", "seguro") else "contact" if has("phone", "teléfono", "telefono") else None)
        hits = [i for i in wrong if not cat or i["category"] == cat]
        acc = L.get("fact_accuracy")
        if not hits:
            return ((f"No encontramos errores de ese tipo. La IA dio bien tus datos en el {acc}% de las respuestas." if es else
                     f"No errors of that kind right now. AI got your facts right in {acc}% of answers."), "truth")
        lines = [f"{i['assistant']} dice “{_val(i['category'], i['ai_says'], es)}” en {i['fact'].lower()} "
                 f"(verdadero: {_val(i['category'], i['truth'], es)})" if es else
                 f"{i['assistant']} says “{_val(i['category'], i['ai_says'], es)}” for {i['fact'].lower()} "
                 f"(true: {_val(i['category'], i['truth'], es)})" for i in hits[:4]]
        src = (f" Fuente probable: {cause['label']}." if es else f" Likely source: {cause['label']}.") if cause else ""
        return ((f"No del todo. Datos correctos: {acc}%. " if es else f"Not entirely. Fact accuracy: {acc}%. ")
                + "; ".join(lines) + "." + src), "issues"

    if has("source", "fuente", "where does", "de dónde", "de donde", "rely", "lee", "reads"):
        if not c["sources"]:
            return ("Aún no hay fuentes registradas." if es else "No sources recorded yet."), "perception"
        top = ", ".join(f"{s['label']} ({s['cited']})" for s in c["sources"][:4])
        extra = (f" {cause['label']} parece causar datos incorrectos: {cause['wrong_share']}% de las respuestas que lo citan tienen un error."
                 if es else f" {cause['label']} looks like the cause of wrong facts: {cause['wrong_share']}% of answers citing it had an error.") if cause else ""
        return ((f"Lo que más leen los asistentes sobre ti: {top}." if es else f"What the assistants read most about you: {top}.") + extra), "perception"

    if has("spanish", "español", "espanol", "latino", "hispan"):
        return ((f"En inglés te nombran en el {L.get('inclusion_en')}% de las respuestas y en español en el {L.get('inclusion_es')}%. "
                 "Aprobar el texto bilingüe de las soluciones es el paso con más impacto en tu plan." if es else
                 f"AI names you in {L.get('inclusion_en')}% of English answers and {L.get('inclusion_es')}% of Spanish ones. "
                 "Approving the bilingual fix text is the biggest step in your growth plan."), "growth")

    if has("sales", "ventas", "money", "dinero", "customers", "clientes", "jobs", "trabajos", "worth", "vale", "roi", "pay"):
        if not g.get("extra_month3"):
            return ("La proyección de ventas está en los planes Plata y Oro." if es else
                    "The sales projection is in the Silver and Gold plans."), "growth"
        roi = (f" Eso es {g['roi']} veces el costo del plan." if es else f" That's {g['roi']}x the plan's cost.") if g.get("roi") else ""
        return ((f"Estimamos unos {g['extra_jobs_month3']} trabajos más al mes para el mes 3 (≈{_money(g['extra_month3'])} al mes), "
                 f"y entre {_money(g['extra_90_low'])} y {_money(g['extra_90_high'])} más en 90 días.{roi}" if es else
                 f"We estimate about {g['extra_jobs_month3']} more jobs a month by month 3 (≈{_money(g['extra_month3'])} a month), "
                 f"and {_money(g['extra_90_low'])}–{_money(g['extra_90_high'])} more over 90 days.{roi}"), "growth")

    if has("why", "por qué", "porque", "score", "low", "bajo", "visib", "show up", "aparezco", "not showing", "no salgo"):
        weak = c["weakest_questions"][0] if c["weakest_questions"] else None
        parts = [f"La IA te nombra en el {L.get('inclusion_rate')}% de las respuestas." if es else
                 f"AI names you in {L.get('inclusion_rate')}% of answers."]
        if weak:
            parts.append(f"Tu punto más débil: “{weak['need']}” ({weak['inclusion']}%)." if es else
                         f"Your weakest question: “{weak['need']}” ({weak['inclusion']}%).")
        if inst:
            parts.append(f"Ahí suelen nombrar a {inst[0]['name']}." if es else f"There, AI usually names {inst[0]['name']}.")
        if c["never_mentioned"]:
            parts.append(f"La IA nunca menciona: {', '.join(c['never_mentioned'][:3])}. Publícalo claro en tu sitio y perfiles." if es else
                         f"AI never mentions: {', '.join(c['never_mentioned'][:3])}. Say it clearly on your site and profiles.")
        return " ".join(parts), "perception"

    return ((f"Resumen: te nombran en el {L.get('inclusion_rate')}% de las respuestas, datos correctos {L.get('fact_accuracy')}%, "
             f"{len(wrong)} datos incorrectos abiertos. Pregúntame qué arreglar primero, quién aparece más que tú o si tus precios están bien."
             if es else
             f"Summary: AI names you in {L.get('inclusion_rate')}% of answers, fact accuracy is {L.get('fact_accuracy')}%, "
             f"and {len(wrong)} wrong facts are open. Ask me what to fix first, which competitor shows up more, or whether your prices are right."),
            "overview")


def answer(db, business_id: int, question: str, history: list[dict], lang: str) -> dict:
    es = lang == "es" or bool(ES_HINTS.search(question))
    c = context(db, business_id)
    text, tab = _rule_answer(question, c, es)
    if agents.is_demo():
        return {"answer": text, "tab": tab, "mode": "demo"}
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    prompt = f"""You are the Aparece assistant for a small-business owner. Answer ONLY from the data below.
If the data doesn't answer the question, say so and suggest what to check. Never invent numbers, prices,
competitors or sources. Plain, friendly language for a non-technical owner. At most 120 words.
Answer in {'Spanish' if es else 'English'}. Mention specific numbers from the data. End with one concrete next step.

Business data (JSON):
{json.dumps(c, ensure_ascii=False)}

Conversation so far:
{convo}

Owner's question: {question}"""
    try:
        return {"answer": agents.chat(prompt).strip() or text, "tab": tab, "mode": "live"}
    except Exception:
        return {"answer": text, "tab": tab, "mode": "demo"}
