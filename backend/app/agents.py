"""The AI agents. Each has one narrow job.

Live mode calls real assistants (ChatGPT, Claude, Gemini, Perplexity) for whichever API keys are set.
Demo mode simulates assistant answers so the full workflow runs with no keys.
Set DEMO_MODE=true|false|auto (auto = demo only when no keys are present).
"""
import hashlib
import json
import os
import random
from collections import defaultdict
import re


def _load_dotenv():
    """Read backend/.env so keys work without exporting them by hand. Real environment variables win."""
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if k.strip() and v and k.strip() not in os.environ:
                os.environ[k.strip()] = v


_load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar")
DEMO_MODE = os.getenv("DEMO_MODE", "auto").lower()

CLAUDE_ASSISTANT_MODEL = os.getenv("CLAUDE_ASSISTANT_MODEL", "claude-sonnet-5-5")
CLAUDE_UTILITY_MODEL = os.getenv("CLAUDE_UTILITY_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_WEB_TOOL = os.getenv("OPENAI_WEB_TOOL", "web_search")
MAX_JOURNEYS = int(os.getenv("MAX_JOURNEYS", "12"))
# Languages each free-scan question is asked in (templates exist for en and es; add more by adding templates).
SCAN_LANGUAGES = [x.strip() for x in os.getenv("SCAN_LANGUAGES", "en,es").split(",") if x.strip()]

DEMO_PROVIDERS = ["chatgpt", "claude", "gemini", "perplexity"]
DAYS_ES = {"monday": "lunes", "tuesday": "martes", "wednesday": "miércoles", "thursday": "jueves",
           "friday": "viernes", "saturday": "sábado", "sunday": "domingo"}


def live_providers() -> list[str]:
    out = []
    if OPENAI_KEY:
        out.append("chatgpt")
    if ANTHROPIC_KEY:
        out.append("claude")
    if GEMINI_KEY:
        out.append("gemini")
    if PERPLEXITY_KEY:
        out.append("perplexity")
    return out


def is_demo() -> bool:
    return DEMO_MODE == "true" or (DEMO_MODE == "auto" and not live_providers())


def providers() -> list[str]:
    return DEMO_PROVIDERS if is_demo() else live_providers()


# ---------------------------------------------------------------- LLM plumbing

def _claude(prompt: str, model: str, web: bool = False, max_tokens: int = 1500) -> str:
    import anthropic
    client = anthropic.Anthropic()
    kwargs = dict(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    if web:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    msg = client.messages.create(**kwargs)
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _claude_web(prompt: str, model: str) -> tuple[str, list[dict]]:
    """Claude with web search. Returns the answer and the pages it cited (or searched, if none were cited)."""
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}])
    text, cited, searched = "", [], []
    for b in msg.content:
        kind = getattr(b, "type", "")
        if kind == "text":
            text += b.text
            cited += [{"url": c.url, "title": getattr(c, "title", "") or ""}
                      for c in (getattr(b, "citations", None) or []) if getattr(c, "url", None)]
        elif kind == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
            searched += [{"url": r.url, "title": getattr(r, "title", "") or ""}
                         for r in b.content if getattr(r, "url", None)]
    return text, cited or searched


def _openai_web(prompt: str) -> tuple[str, list[dict]]:
    """ChatGPT with web search. Returns the answer and the URLs it cited."""
    from openai import OpenAI
    resp = OpenAI().responses.create(model=OPENAI_MODEL, input=prompt, tools=[{"type": OPENAI_WEB_TOOL}])
    sources = []
    for item in getattr(resp, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            sources += [{"url": a.url, "title": getattr(a, "title", "") or ""}
                        for a in (getattr(part, "annotations", None) or [])
                        if getattr(a, "type", "") == "url_citation" and getattr(a, "url", None)]
    return resp.output_text, sources


def _openai(prompt: str, web: bool = False) -> str:
    from openai import OpenAI
    client = OpenAI()
    kwargs = dict(model=OPENAI_MODEL, input=prompt)
    if web:
        kwargs["tools"] = [{"type": OPENAI_WEB_TOOL}]
    return client.responses.create(**kwargs).output_text


def _post_json(url: str, body: dict, headers: dict, timeout: int = 60) -> dict:
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_gemini(data: dict) -> tuple[str, list[dict]]:
    """Answer text + the web pages Google Search grounded it on (groundingMetadata.groundingChunks)."""
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    sources = []
    for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks", []):
        web = ch.get("web") or {}
        if web.get("uri"):
            # Gemini returns a redirect link; the title carries the real site's domain.
            title = web.get("title") or ""
            url = web["uri"] if "grounding-api-redirect" not in web["uri"] or "." not in title else f"https://{title}"
            sources.append({"url": url, "title": title})
    return text, sources


def _gemini(prompt: str, search: bool = True) -> tuple[str, list[dict]]:
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if search:
        body["tools"] = [{"google_search": {}}]
    data = _post_json(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                      body, {"x-goog-api-key": GEMINI_KEY})
    return parse_gemini(data)


def parse_perplexity(data: dict) -> tuple[str, list[dict]]:
    """Answer text + sources from search_results (current) or citations (older responses)."""
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    sources = [{"url": s["url"], "title": s.get("title", "")} for s in data.get("search_results") or [] if s.get("url")]
    if not sources:
        sources = [{"url": u, "title": ""} for u in data.get("citations") or [] if isinstance(u, str)]
    return text, sources


def _perplexity(prompt: str) -> tuple[str, list[dict]]:
    data = _post_json("https://api.perplexity.ai/chat/completions",
                      {"model": PERPLEXITY_MODEL, "messages": [{"role": "user", "content": prompt}]},
                      {"Authorization": f"Bearer {PERPLEXITY_KEY}"})
    return parse_perplexity(data)


def _utility(prompt: str) -> str:
    """Cheap model for extraction and drafting."""
    if ANTHROPIC_KEY:
        return _claude(prompt, CLAUDE_UTILITY_MODEL)
    if OPENAI_KEY:
        return _openai(prompt)
    if GEMINI_KEY:
        return _gemini(prompt, search=False)[0]
    raise RuntimeError("No key for reading answers")


def model_for(provider: str) -> str:
    return {"claude": CLAUDE_ASSISTANT_MODEL, "chatgpt": OPENAI_MODEL, "gemini": GEMINI_MODEL,
            "perplexity": PERPLEXITY_MODEL}.get(provider, provider)


def chat(prompt: str) -> str:
    """The owner-facing assistant uses the stronger model; no web access, it answers from supplied data."""
    if ANTHROPIC_KEY:
        return _claude(prompt, CLAUDE_ASSISTANT_MODEL, max_tokens=600)
    if OPENAI_KEY:
        return _openai(prompt)
    return _gemini(prompt, search=False)[0]


def parse_json(text: str):
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON found in model output")
    return json.loads(text[start:text.rfind("]" if text[start] == "[" else "}") + 1])


def fact_name(fact: dict, lang: str = "en") -> str:
    """'Price' of product 'Leather huaraches' -> 'Leather huaraches price'."""
    label = fact["label"] if lang == "en" else (fact.get("label_es") or fact["label"])
    product = fact.get("product") or ""
    low = label if label[:2].isupper() else label.lower()  # keep acronyms like RAM, SSD
    if lang == "es":
        product = fact.get("product_es") or product
        return f"{low} de {product}" if product else label
    return f"{product} {low}" if product else label


def display_value(fact: dict, value: str, lang: str = "en") -> str:
    cat = fact["category"]
    out = "out" in value.lower()
    if cat == "stock":
        return ("Sold out" if out else "In stock") if lang == "en" else ("Agotado" if out else "Disponible")
    if cat == "shipping":
        return f"{value} days" if lang == "en" else f"{value} días"
    if cat == "returns":
        if value in {"none", "0"}:
            return "No returns" if lang == "en" else "Sin devoluciones"
        return f"{value} days" if lang == "en" else f"{value} días"
    if cat == "price":
        return f"${value}"
    if cat == "warranty":
        if value in {"none", "0"}:
            return "No warranty" if lang == "en" else "Sin garantía"
        return f"{value} months" if lang == "en" else f"{value} meses"
    if cat in {"feature", "insurance"}:
        yes = value.lower() in {"yes", "sí", "si"}
        return ("Yes" if yes else "No") if lang == "en" else ("Sí" if yes else "No")
    if cat == "license" and value.strip().lower() in {"none", "no", "not licensed", "unlicensed"}:
        return "Not licensed" if lang == "en" else "Sin licencia"
    return value


def is_local(biz: dict) -> bool:
    return biz.get("segment") in {"services", "trades", "cleaning", "restaurant"}


def is_shop(biz: dict) -> bool:
    """E-commerce and tech both sell products online; only services are local-first."""
    return biz.get("segment") in {"ecommerce", "tech"}


def _rng(*parts) -> random.Random:
    seed = int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)
    return random.Random(seed)


# ------------------------------------------------------------ Journey Agent

def template_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    """Customer questions built from the verified profile, in English and Spanish."""
    city, cat = biz["city"], biz["category"]
    cat_es = biz.get("category_es") or cat
    js = []

    def add(q_en, q_es, category, related):
        js.append({"question": q_en, "language": "en", "category": category, "related_facts": related})
        js.append({"question": q_es, "language": "es", "category": category, "related_facts": related})

    prices = [f["key"] for f in facts if f["category"] == "price"]
    hours = [f for f in facts if f["category"] == "hours"]
    add(f"What is the best {cat} in {city}?", f"¿Cuál es el mejor {cat_es} en {city}?",
        "General", (prices[:1] + [h["key"] for h in hours[:1]]))
    for f in facts:
        label, label_es = f["label"], f.get("label_es") or f["label"]
        if f["category"] == "service" and f["value"].lower() in {"yes", "sí", "si"}:
            add(f"Where can I get {label.lower()} in {city}?",
                f"¿Dónde encuentro {label_es.lower()} en {city}?", label, [f["key"]] + prices[:1])
        elif f["category"] == "hours" and f["value"] != "closed":
            day = f["key"].split(".")[-1]
            add(f"Which {cat} is open on {day.title()} in {city}?",
                f"¿Qué {cat_es} abre el {DAYS_ES.get(day, day)} en {city}?", f"Open {day.title()}", [f["key"]])
        elif f["category"] == "language" and f["value"].lower() in {"yes", "sí", "si"}:
            add(f"Is there a {cat} in {city} where the staff speak Spanish?",
                f"¿Hay un {cat_es} en {city} donde hablen español?", "Spanish-speaking", [f["key"]])
        elif f["category"] == "price":
            add(f"How much does {label.lower()} cost at a {cat} in {city}?",
                f"¿Cuánto cuesta {label_es.lower()} en un {cat_es} en {city}?", label, [f["key"]])
    return js[:MAX_JOURNEYS * 2]


def ecommerce_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    """Shopping questions per product, plus store-policy and brand questions."""
    js = []

    def add(q_en, q_es, category, related):
        js.append({"question": q_en, "language": "en", "category": category, "related_facts": related})
        js.append({"question": q_es, "language": "es", "category": category, "related_facts": related})

    products = {}
    for f in facts:
        if f.get("product"):
            products.setdefault(f["product"], {"es": f.get("product_es") or f["product"], "facts": []})
            products[f["product"]]["facts"].append(f)
    store = [f["key"] for f in facts if not f.get("product") and f["category"] in {"shipping", "returns"}]
    for name, p in products.items():
        keys = [f["key"] for f in p["facts"]]
        price = next((f for f in p["facts"] if f["category"] == "price"), None)
        cap = ""
        if price:
            try:
                cap = f" under ${int(-(-float(price['value']) // 25) * 25)}"
            except ValueError:
                cap = ""
        add(f"What are the best {name.lower()}{cap}?",
            f"¿Cuáles son los mejores {p['es'].lower()}{cap.replace('under', 'por menos de')}?",
            name, keys)
        add(f"Where can I buy {name.lower()} online with fast shipping?",
            f"¿Dónde compro {p['es'].lower()} en línea con envío rápido?", name, keys[:2] + store[:1])
    if store:
        add(f"What is the return policy at {biz['name']}?",
            f"¿Cuál es la política de devoluciones de {biz['name']}?", "Store policies", store)
    add(f"Is {biz['name']} a trustworthy online store?",
        f"¿{biz['name']} es una tienda en línea confiable?", "Store policies", store)
    return js[:MAX_JOURNEYS * 2]


def tech_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    """Tech shoppers compare specs and budgets, and ask about warranty before buying refurbished."""
    js = []

    def add(q_en, q_es, category, related):
        js.append({"question": q_en, "language": "en", "category": category, "related_facts": related})
        js.append({"question": q_es, "language": "es", "category": category, "related_facts": related})

    products = {}
    for f in facts:
        if f.get("product"):
            products.setdefault(f["product"], {"es": f.get("product_es") or f["product"], "facts": []})
            products[f["product"]]["facts"].append(f)
    warranty = [f["key"] for f in facts if f["category"] == "warranty"]
    returns = [f["key"] for f in facts if f["category"] == "returns"]
    for name, p in products.items():
        by_cat = defaultdict(list)
        for f in p["facts"]:
            by_cat[f["category"]].append(f["key"])
        price = next((f for f in p["facts"] if f["category"] == "price"), None)
        try:
            budget = int(-(-float(price["value"]) // 100) * 100) if price else 500
        except ValueError:
            budget = 500
        add(f"Is the {name} a good buy under ${budget}?",
            f"¿El {p['es']} es buena compra por menos de ${budget}?",
            name, by_cat["price"] + by_cat["stock"] + by_cat["spec"][:1])
        if by_cat["spec"] or by_cat["feature"]:
            add(f"What are the specs of the {name}? Is it worth it?",
                f"¿Qué especificaciones tiene el {p['es']}? ¿Vale la pena?",
                name, by_cat["spec"] + by_cat["feature"])
    add("Where can I buy refurbished laptops and phones online with a good warranty?",
        "¿Dónde compro laptops y celulares reacondicionados en línea con buena garantía?",
        "Warranty", warranty + returns)
    add(f"What warranty does {biz['name']} give on refurbished devices?",
        f"¿Qué garantía da {biz['name']} en equipos reacondicionados?", "Store policies", warranty + returns)
    return js[:MAX_JOURNEYS * 2]


def trades_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    """Homeowners ask about trust first (licensed, insured), then price, area and language."""
    city, cat = biz["city"], biz["category"]
    cat_es = biz.get("category_es") or cat
    js = []

    def add(q_en, q_es, category, related):
        js.append({"question": q_en, "language": "en", "category": category, "related_facts": related})
        js.append({"question": q_es, "language": "es", "category": category, "related_facts": related})

    keys = lambda *cats: [f["key"] for f in facts if f["category"] in cats]  # noqa: E731
    add(f"Who is the best {cat} in {city}?", f"¿Quién es el mejor {cat_es} en {city}?", "General",
        keys("license", "price")[:2])
    add(f"Find me a licensed and insured {cat} in {city}", f"Busco un {cat_es} con licencia y seguro en {city}",
        "Licensed and insured", keys("license", "insurance"))
    for f in facts:
        if f["category"] == "service" and f["value"].lower() in {"yes", "sí", "si"}:
            add(f"{cat[:1].upper() + cat[1:]} in {city} with {f['label'].lower()}?",
                f"¿{cat_es[:1].upper() + cat_es[1:]} en {city} con {(f.get('label_es') or f['label']).lower()}?",
                f["label"], [f["key"]] + keys("price")[:1])
    add(f"Is there a {cat} near {city} where they speak Spanish?", f"¿Hay algún {cat_es} cerca de {city} que hable español?",
        "Spanish-speaking", keys("language", "contact"))
    add(f"Which {cat} companies serve my area around {city}, and how do I call them?",
        f"¿Qué empresas de {cat_es} dan servicio en mi zona cerca de {city} y cómo las llamo?",
        "Service area", keys("service_area", "contact", "hours"))
    return js[:MAX_JOURNEYS * 2]


def cleaning_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    """What people ask when hiring cleaners: price, trust, what's included, area, timing, language."""
    city, cat = biz["city"], biz["category"]
    cat_es = biz.get("category_es") or cat
    js = []

    def add(q_en, q_es, category, related):
        js.append({"question": q_en, "language": "en", "category": category, "related_facts": related})
        js.append({"question": q_es, "language": "es", "category": category, "related_facts": related})

    keys = lambda *cats: [f["key"] for f in facts if f["category"] in cats]  # noqa: E731
    svc = {f["key"].split(".")[-1]: f["key"] for f in facts if f["category"] == "service"}
    add(f"What is the best {cat} in {city}?", f"¿Cuál es el mejor {cat_es} en {city}?", "Best in town",
        keys("price", "insurance")[:2])
    add(f"How much does a deep clean cost for a 3-bedroom house in {city}?",
        f"¿Cuánto cuesta una limpieza profunda de una casa de 3 recámaras en {city}?", "Deep clean price",
        keys("price"))
    add(f"Move-out cleaning near {city} this week", f"Limpieza de mudanza cerca de {city} esta semana",
        "Move-out cleaning", [k for k in (svc.get("move_out"), svc.get("same_week")) if k] + keys("service_area")[:1])
    add(f"Insured, background-checked house cleaners in {city}",
        f"Limpiadoras con seguro y revisión de antecedentes en {city}", "Insured and checked",
        keys("insurance") + [k for k in (svc.get("background_check"),) if k])
    add(f"House cleaners in {city} who bring their own supplies",
        f"Limpieza de casas en {city} que traiga sus propios productos", "Supplies included",
        [k for k in (svc.get("supplies"), svc.get("eco")) if k])
    add(f"Office cleaning on weekends in {city}", f"Limpieza de oficinas los fines de semana en {city}",
        "Weekend office cleaning", [k for k in (svc.get("office"),) if k] + keys("hours"))
    add(f"Cleaning service in {city} that speaks Spanish", f"Servicio de limpieza en {city} que hable español",
        "Spanish-speaking", keys("language", "contact"))
    return js[:MAX_JOURNEYS * 2]


def generate_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    fallback = {"ecommerce": ecommerce_journeys, "tech": tech_journeys,
                "trades": trades_journeys, "cleaning": cleaning_journeys,
                "restaurant": restaurant_journeys}.get(biz.get("segment"), template_journeys)
    if is_demo():
        return fallback(biz, facts)
    keys = [f["key"] for f in facts]
    kind = {"ecommerce": "an online store (e-commerce) that ships products",
            "tech": "an online store selling tech products (laptops, phones, accessories); shoppers compare "
                    "specs, budgets like 'under $500', warranty and compatibility",
            "cleaning": "a local cleaning service (house, deep, move-out, office); customers ask about price, "
                        "insurance, background checks, supplies, service area, same-week availability and Spanish",
            "trades": "a local contractor (home repair, roofing, remodeling); homeowners ask about license, "
                      "insurance, free estimates, service area, emergency service and Spanish"}.get(
        biz.get("segment"), "a local service business")
    prompt = f"""You write realistic questions shoppers ask AI assistants.
Business type: {biz['category']}, {kind}, based in {biz['city']}.
Its verified facts (keys): {keys}
Write {MAX_JOURNEYS} questions: half in English, half in natural U.S. Spanish (Spanglish is fine).
Cover different customer needs (price, specific products or services, availability, shipping,
returns, hours, specialties, specs, features, warranty, language). Use a product's name as the category for product questions.
Never mention the business name. Return ONLY a JSON array of objects:
{{"question": str, "language": "en"|"es", "category": short need label in English,
 "related_facts": [fact keys from the list that the question is about]}}"""
    try:
        return parse_json(_utility(prompt))[:MAX_JOURNEYS]
    except Exception:
        return fallback(biz, facts)


# Placeholder rivals so a free check can simulate answers before the owner names real competitors.
DEFAULT_COMPETITORS = {
    "services": ["A national chain", "Top-rated local rival", "Franchise location nearby", "Budget competitor"],
    "ecommerce": ["Big-box marketplace seller", "Top-rated online rival", "Discount online store", "Brand-name retailer"],
    "tech": ["Big-box electronics outlet", "Refurb marketplace seller", "Discount laptop store", "Brand-name retailer"],
    "restaurant": ["Popular chain restaurant", "Top-rated local spot", "Food truck nearby", "Delivery-app favorite"],
    "cleaning": ["National cleaning franchise", "Top-rated local cleaners", "Gig-app cleaner", "Budget maid service"],
    "trades": ["National home-services franchise", "Top-rated local contractor", "Lead-gen marketplace pro",
               "Budget handyman service"],
}


def standard_key(category: str, label: str) -> str:
    """Keys the journey and phrasing code understands, for facts typed during a free check."""
    if category == "hours":
        return f"hours.{label.split()[0].lower()}"
    return {"license": "credential.license", "insurance": "credential.insurance", "service_area": "area.service",
            "contact": "contact.phone", "warranty": "store.warranty", "returns": "store.returns",
            "shipping": "store.shipping", "language": "language.spanish"}.get(category, "")


def _restaurant_questions(biz: dict, keys: list, features: list | None) -> list[dict]:
    """What diners actually ask: the food, the city, and the thing they need right now."""
    city, name = biz["city"], biz["name"]
    c = biz.get("cuisine") or {"en": "food", "es": "comida"}
    en, es = c["en"], c["es"]
    pairs = [
        (f"Where can I get the best {en} in {city}?", f"¿Cuáles son los mejores lugares de {es} en {city}?", "Best in town"),
        (f"{en[:1].upper() + en[1:]} open late in {city}", f"Lugares de {es} abiertos de noche en {city}", "Open late"),
        (f"Good {en} in {city} with vegetarian options", f"Lugares de {es} con opciones vegetarianas en {city}", "Vegetarian options"),
        (f"Cheap and good {en} in {city} with great reviews", f"Lugares de {es} buenos y baratos en {city}", "Prices and reviews"),
        (f"{en[:1].upper() + en[1:]} with takeout or delivery in {city}", f"{es[:1].upper() + es[1:]} para llevar o a domicilio en {city}",
         "Takeout or delivery"),
        (f"What do you know about {name}? Is it a good choice?", f"¿Qué sabes de {name}? ¿Es buena opción?", "About your business"),
    ]
    covered = {"Vegetarian options", "Takeout", "Delivery", "Late night"}
    for s in [f for f in (features or []) if f["label"] not in covered][:2]:
        pairs.append((f"{en[:1].upper() + en[1:]} in {city} with {s['label'].lower()}",
                      f"{es[:1].upper() + es[1:]} en {city} con {(s.get('label_es') or s['label']).lower()}", s["label"]))
    return [{"question": q, "language": lang, "category": cat, "related_facts": keys}
            for e, s_, cat in pairs for lang, q in (("en", e), ("es", s_)) if lang in SCAN_LANGUAGES]


def restaurant_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    return _restaurant_questions(biz, [f["key"] for f in facts], [])


def check_journeys(biz: dict, facts: list[dict], services: list[dict] | None = None) -> list[dict]:
    """Free AI Check: four customer questions in English and Spanish, plus one per service found on the website."""
    cat, cat_es, city, name = biz["category"], biz.get("category_es") or biz["category"], biz["city"], biz["name"]
    keys = [f["key"] for f in facts]
    if biz.get("segment") == "restaurant":
        return _restaurant_questions(biz, keys, services)
    shop = is_shop(biz)
    where, where_es = ("online", "en línea") if shop else (f"in {city}", f"en {city}")
    pairs = [
        (f"What is the best {cat} {where}?", f"¿Cuál es el mejor {cat_es} {where_es}?", "Best in category"),
        (f"Which {cat} {where} has fair prices and good reviews?",
         f"¿Qué {cat_es} {where_es} tiene buenos precios y buenas reseñas?", "Prices and reviews"),
        (f"Which {cat} {where} is open on weekends?", f"¿Qué {cat_es} {where_es} abre los fines de semana?",
         "Open on weekends"),
        (f"What do you know about {name}? Is it a good choice?", f"¿Qué sabes de {name}? ¿Es buena opción?",
         "About your business"),
    ]
    for s in (services or [])[:3]:  # "Who does move-out cleaning in Houston?": the questions that bring jobs
        pairs.append((f"Who offers {s['label'].lower()} {where}?",
                      f"¿Quién ofrece {(s.get('label_es') or s['label']).lower()} {where_es}?", s["label"]))
    # Every question is asked in each scan language; results are combined per question, not compared by language.
    js = []
    for en, es, category in pairs:
        for lang, q in (("en", en), ("es", es)):
            if lang in SCAN_LANGUAGES:
                js.append({"question": q, "language": lang, "category": category, "related_facts": keys})
    return js


# -------------------------------------------------------- Query Runner (live)

def ask_assistant(provider: str, question: str, city: str) -> tuple[str, list[dict]]:
    """Returns (answer, sources). Sources are the web pages the assistant cited: what it relied on."""
    # APIs have no GPS location, so we state the city the way a local user's app would.
    prompt = f"{question}\n\n(I'm located in {city}.)" if city else question
    if provider == "claude":
        return _claude_web(prompt, CLAUDE_ASSISTANT_MODEL)
    if provider == "chatgpt":
        return _openai_web(prompt)
    if provider == "gemini":
        return _gemini(prompt)
    if provider == "perplexity":
        return _perplexity(prompt)
    raise ValueError(f"Unsupported provider {provider}")


# ------------------------------------------------------------ Sources

SOURCE_KINDS = [  # (domain fragment, kind, label)
    ("google.", "profile", "Google Business Profile / Maps"), ("maps.apple", "profile", "Apple Maps"),
    ("yelp.", "reviews", "Yelp"), ("angi.", "reviews", "Angi"), ("thumbtack.", "reviews", "Thumbtack"), ("homeadvisor.", "reviews", "HomeAdvisor"),
    ("bbb.org", "reviews", "Better Business Bureau"), ("nextdoor.", "reviews", "Nextdoor"),
    ("facebook.", "social", "Facebook"), ("instagram.", "social", "Instagram"), ("tiktok.", "social", "TikTok"),
    ("yellowpages.", "directory", "Yellow Pages"), ("manta.", "directory", "Manta"),
    ("superpages.", "directory", "Superpages"), ("mapquest.", "directory", "MapQuest"),
    ("amazon.", "marketplace", "Amazon"), ("ebay.", "marketplace", "eBay"), ("etsy.", "marketplace", "Etsy"),
    ("backmarket.", "marketplace", "Back Market"), ("walmart.", "marketplace", "Walmart"),
    ("reddit.", "forum", "Reddit"), ("quora.", "forum", "Quora"),
]


def domain_of(url: str) -> str:
    d = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    return d[4:] if d.startswith("www.") else d


def classify_source(domain: str, biz: dict) -> tuple[str, str]:
    own = domain_of(biz.get("website") or "")
    if own and (domain == own or domain.endswith("." + own)):
        return "own", "Your website"
    for frag, kind, label in SOURCE_KINDS:
        if frag in domain:
            return kind, label
    return "other", domain


# What a demo assistant "reads". The stale listing is where old or wrong facts come from.
DEMO_SOURCES = {
    "trades": ["google.com/maps", "yelp.com", "angi.com", "nextdoor.com", "bbb.org"],
    "cleaning": ["google.com/maps", "yelp.com", "thumbtack.com", "angi.com", "nextdoor.com", "facebook.com"],
    "restaurant": ["google.com/maps", "yelp.com", "tripadvisor.com", "instagram.com", "doordash.com", "reddit.com"],
    "services": ["google.com/maps", "yelp.com", "facebook.com", "nextdoor.com"],
    "ecommerce": ["etsy.com", "ebay.com", "instagram.com", "reddit.com"],
    "tech": ["ebay.com", "amazon.com", "reddit.com", "backmarket.com"],
}
DEMO_STALE = {"restaurant": "yellowpages.com", "cleaning": "yellowpages.com", "trades": "yellowpages.com", "services": "yellowpages.com", "ecommerce": "ebay.com/old-listing",
              "tech": "ebay.com/old-listing"}
DESCRIPTORS = {
    "restaurant": (["authentic", "great salsa", "fast service", "fair prices", "friendly staff", "late-night spot"],
                   ["long lines", "small space"]),
    "cleaning": (["reliable", "thorough", "fair prices", "eco-friendly", "Spanish-speaking", "same-week openings"],
                 ["hard to book", "small team"]),
    "trades": (["family-owned", "free estimates", "storm repair", "fair prices", "fast response", "Spanish-speaking"],
               ["hard to reach", "small crew"]),
    "services": (["honest", "fair prices", "friendly", "Spanish-speaking", "quick service"], ["long waits"]),
    "ecommerce": (["handmade", "quality leather", "authentic", "gift-worthy", "bilingual support"], ["slow shipping"]),
    "tech": (["affordable", "tested devices", "good warranty", "good battery life"], ["older models", "limited stock"]),
}


# ------------------------------------------------- Claim Extraction Agent

FORMAT_HINT = {
    "hours": '"HH:MM-HH:MM" in 24h time, or "closed"',
    "price": "a number in USD, no $ sign",
    "service": '"yes" or "no"',
    "language": '"yes" or "no"',
    "contact": "the phone number",
    "stock": '"in stock" or "out of stock"',
    "shipping": 'delivery time in days, like "3-5"',
    "returns": 'return window in days, like "30", or "none"',
    "spec": 'number with unit, like "16 GB" or "14 in"',
    "feature": '"yes" or "no"',
    "warranty": 'warranty length in months, like "12", or "none"',
    "license": 'the license or registration number, or "not licensed"',
    "insurance": '"yes" or "no"',
    "service_area": "comma-separated list of cities served",
}


def extract(answer: str, biz: dict, facts: list[dict], competitors: list[str]) -> dict:
    fact_lines = "\n".join(
        f'- {f["key"]}: {fact_name(f)}, format {FORMAT_HINT.get(f["category"], "short text")}' for f in facts)
    prompt = f"""Analyze an AI assistant's answer to a shopper.
Business we monitor: "{biz['name']}" (match close spelling variants).
Known competitors: {competitors}
Fact keys you may report, with required formats:
{fact_lines}

Return ONLY JSON:
{{"mentioned": bool, "position": 1-based rank of the business among businesses listed or null,
 "competitors": [other business names mentioned],
 "claims": [{{"fact_key": key from the list, "value": value in the required format}}],
 "description": one sentence, in English, on how the answer describes "{biz['name']}" ("" if not mentioned),
 "descriptors": [up to 5 short words or phrases the answer associates with "{biz['name']}"],
 "sentiment": "positive" | "neutral" | "negative" (how the answer presents "{biz['name']}")}}
Only include claims the answer makes about "{biz['name']}" itself. Do not guess.

Answer:
\"\"\"{answer}\"\"\""""
    try:
        data = parse_json(_utility(prompt))
        return {"mentioned": bool(data.get("mentioned")), "position": data.get("position"),
                "competitors": data.get("competitors", []), "claims": data.get("claims", []),
                "description": data.get("description") or "", "descriptors": data.get("descriptors") or [],
                "sentiment": data.get("sentiment") or "neutral"}
    except Exception:  # no model available to read it: read it with code instead of guessing
        from .reader import read_answer
        return read_answer(answer, biz, facts, competitors)


# ------------------------------------------------------ Demo simulator

def _distort(fact: dict) -> str | None:
    cat, v = fact["category"], fact["value"]
    if cat == "hours":
        return "closed" if v != "closed" else "09:00-17:00"
    if cat == "price":
        try:
            return f"{float(v) * 0.75:.2f}"
        except ValueError:
            return None
    if cat in {"service", "language"}:
        return "no" if v.lower() in {"yes", "sí", "si"} else "yes"
    if cat == "stock":
        return "out of stock" if "in" in v.lower() else "in stock"
    if cat == "shipping":
        return "7-10"
    if cat == "returns":
        return "none" if v not in {"none", "0"} else "30"
    if cat == "spec":
        m = re.match(r"(\d+(?:\.\d+)?)(.*)", v.strip())
        return f"{float(m.group(1)) / 2:g}{m.group(2)}" if m else None
    if cat == "feature":
        return "no" if v.lower() in {"yes", "sí", "si"} else "yes"
    if cat == "warranty":
        return "3" if v != "3" else "none"
    if cat == "license":
        return "not licensed"
    if cat == "insurance":
        return "no" if v.lower() in {"yes", "sí", "si"} else "yes"
    if cat == "service_area":
        return "Fort Worth, Arlington"
    if cat == "contact":
        digits = re.sub(r"\D", "", v)
        return f"({digits[:3]}) {digits[3:6]}-0199" if len(digits) >= 10 else None
    return None


def _phrase(fact: dict, value: str, lang: str) -> str:
    cat = fact["category"]
    label = fact["label"] if lang == "en" else (fact.get("label_es") or fact["label"])
    if cat == "spec":
        return f"{value} {label}" if lang == "en" else f"{label} de {value}"
    if cat == "feature":
        yes = value.lower() in {"yes", "sí", "si"}
        if lang == "en":
            return f"with {label.lower()}" if yes else f"no {label.lower()}"
        return f"con {label.lower()}" if yes else f"sin {label.lower()}"
    if cat == "warranty":
        if value in {"none", "0"}:
            return "sold as-is with no warranty" if lang == "en" else "sin garantía"
        return f"{value}-month warranty" if lang == "en" else f"garantía de {value} meses"
    if cat == "license":
        if value.strip().lower() in {"none", "no", "not licensed", "unlicensed"}:
            return "no license on file" if lang == "en" else "sin licencia registrada"
        return f"license #{value}" if lang == "en" else f"licencia #{value}"
    if cat == "insurance":
        yes = value.lower() in {"yes", "sí", "si"}
        if lang == "en":
            return "fully insured" if yes else "no proof of insurance"
        return "con seguro" if yes else "sin comprobante de seguro"
    if cat == "service_area":
        return f"serves {value}" if lang == "en" else f"da servicio en {value}"
    prod = (fact.get("product") if lang == "en" else fact.get("product_es") or fact.get("product")) or ""
    if prod:
        label = prod
    if cat == "stock":
        out = "out" in value.lower() or "agotado" in value.lower()
        if lang == "en":
            return "currently sold out" if out else "in stock"
        return "agotado" if out else "disponible"
    if prod and cat == "price":
        return f"for ${value}" if lang == "en" else f"a ${value}"
    if cat == "shipping":
        return f"ships in {value} days" if lang == "en" else f"envío en {value} días"
    if cat == "returns":
        if value in {"none", "0"}:
            return "no returns accepted" if lang == "en" else "no acepta devoluciones"
        return f"{value}-day returns" if lang == "en" else f"devoluciones hasta {value} días"
    if cat == "hours":
        day = fact["key"].split(".")[-1]
        d = day.title() if lang == "en" else DAYS_ES.get(day, day)
        if value == "closed":
            return f"closed on {d}" if lang == "en" else f"cerrado el {d}"
        return f"open {d} {value.replace('-', '–')}" if lang == "en" else f"abre el {d} {value.replace('-', '–')}"
    if cat == "price":
        return f"{label.lower()} around ${value}" if lang == "en" else f"{label.lower()} desde ${value}"
    if cat in {"service", "language"}:
        yes = value.lower() in {"yes", "sí", "si"}
        if lang == "en":
            return f"offers {label.lower()}" if yes else f"doesn't list {label.lower()}"
        return f"ofrece {label.lower()}" if yes else f"no menciona {label.lower()}"
    if cat == "contact":
        return f"call {value}" if lang == "en" else f"teléfono {value}"
    return f"{label}: {value}"


FILLER_EN = ["well reviewed for honest pricing", "popular with locals", "friendly, fast service",
             "strong reviews for customer service"]
FILLER_ES = ["con buenas reseñas por precios justos", "muy popular en la zona", "servicio amable y rápido",
             "buenas opiniones sobre el servicio"]
SHOP_FILLER_EN = ["fast shipping and good reviews", "wide selection", "known for quality craftsmanship",
                  "strong reviews for customer service"]
SHOP_FILLER_ES = ["envíos rápidos y buenas reseñas", "gran variedad", "conocida por su calidad artesanal",
                  "buenas opiniones sobre el servicio"]
FOOD_FILLER_EN = ["great reviews for the food", "popular late-night spot", "fast and affordable", "locals' favorite"]
FOOD_FILLER_ES = ["muy buenas reseñas de la comida", "popular en la noche", "rápido y económico", "el favorito de la zona"]
CLEAN_FILLER_EN = ["great reviews for deep cleans", "flexible scheduling", "eco-friendly products",
                   "background-checked staff"]
CLEAN_FILLER_ES = ["buenas reseñas por limpiezas profundas", "horarios flexibles", "productos ecológicos",
                   "personal con revisión de antecedentes"]
TRADES_FILLER_EN = ["free estimates and good reviews", "family-owned, fast response", "licensed and insured",
                    "popular for storm repairs"]
TRADES_FILLER_ES = ["estimados gratis y buenas reseñas", "negocio familiar, responde rápido", "con licencia y seguro",
                    "popular para reparaciones por tormenta"]
TECH_FILLER_EN = ["certified refurbished with a 90-day warranty", "low prices on older models",
                  "large selection of laptops", "good reviews for battery quality"]
TECH_FILLER_ES = ["reacondicionados certificados con garantía de 90 días", "precios bajos en modelos anteriores",
                  "gran selección de laptops", "buenas reseñas por la calidad de las baterías"]


def simulate(provider: str, journey: dict, biz: dict, facts: list[dict], competitors: list[str],
             scan_round: int, fixed_keys: set, fixed_missed: set) -> tuple[str, dict]:
    """Produces a believable answer plus the extraction it implies.

    Each assistant holds stable 'beliefs' about the business (some wrong).
    Approved fixes change those beliefs on later scans, so before/after is visible.
    """
    lang = journey["language"]
    r = _rng(provider, journey["question"], scan_round)
    base = 0.6 if lang == "en" else 0.3
    if biz["name"].lower() in journey["question"].lower():  # branded question
        base = 0.95
    if (journey["category"], lang) in fixed_missed:
        base += 0.3
    if lang == "es" and any(k.startswith("language.") for k in fixed_keys):
        base += 0.15
    base += {"chatgpt": 0.05, "claude": 0.0, "gemini": -0.05, "perplexity": 0.05}.get(provider, 0)
    mentioned = r.random() < min(base, 0.95)

    by_key = {f["key"]: f for f in facts}
    claims = []
    if mentioned:
        related = [k for k in journey.get("related_facts", []) if k in by_key]
        extra = [k for k in by_key if k not in related]
        r.shuffle(extra)
        for key in (related + extra[:1])[:2]:
            fact = by_key[key]
            wrong_belief = _rng("belief", provider, key).random() < 0.3
            if key in fixed_keys:  # an approved fix usually corrects the assistant's belief
                wrong_belief = wrong_belief and r.random() < 0.15
            value = (_distort(fact) or fact["value"]) if wrong_belief else fact["value"]
            claims.append({"fact_key": key, "value": value})

    comp = competitors[:]
    r.shuffle(comp)
    names = comp[: r.randint(2, 3)]
    position = None
    if mentioned:
        position = r.randint(1, len(names) + 1)
        names.insert(position - 1, biz["name"])

    lines = []
    for i, name in enumerate(names, 1):
        if name == biz["name"]:
            parts, named = [], set()
            for c in claims:
                f = by_key[c["fact_key"]]
                prod = (f.get("product_es") if lang == "es" else None) or f.get("product") or ""
                phrase = _phrase(f, c["value"], lang)
                if prod and prod not in named:
                    phrase = f"{prod.lower()} {phrase}"
                    named.add(prod)
                parts.append(phrase)
            detail = ", ".join(parts) or ("well-rated seller" if lang == "en" else "vendedor bien calificado")
        else:
            pool = {"ecommerce": (SHOP_FILLER_EN, SHOP_FILLER_ES), "tech": (TECH_FILLER_EN, TECH_FILLER_ES),
                    "trades": (TRADES_FILLER_EN, TRADES_FILLER_ES),
                    "cleaning": (CLEAN_FILLER_EN, CLEAN_FILLER_ES),
                    "restaurant": (FOOD_FILLER_EN, FOOD_FILLER_ES)}.get(
                biz.get("segment"), (FILLER_EN, FILLER_ES))[0 if lang == "en" else 1]
            detail = r.choice(pool)
        lines.append(f"{i}. {name}: {detail}.")
    if is_shop(biz):
        intro = "Here are some good places to shop online:" if lang == "en" else "Estas tiendas en línea son buenas opciones:"
        outro = ("Prices and stock change often, so confirm on the store's site." if lang == "en"
                 else "Los precios y el inventario cambian, confirma en la tienda.")
    else:
        intro = (f"Here are a few options in {biz['city']}:" if lang == "en"
                 else f"Aquí tienes algunas opciones en {biz['city']}:")
        outro = (("Ask for a written estimate and check the license before hiring." if lang == "en"
                  else "Pide un estimado por escrito y revisa la licencia antes de contratar.")
                 if biz.get("segment") == "trades" else
                 ("Confirm what’s included and whether they serve your area." if lang == "en"
                  else "Confirma qué incluye y si dan servicio en tu zona.")
                 if biz.get("segment") == "cleaning" else
                 "Check current hours before visiting." if lang == "en" else "Confirma el horario antes de ir.")
    text = "\n".join([intro, *lines, outro])
    seg = biz.get("segment") if biz.get("segment") in DEMO_SOURCES else "services"
    wrong = any(c["value"] != by_key[c["fact_key"]]["value"] for c in claims)
    pool = DEMO_SOURCES[seg][:]
    r.shuffle(pool)
    read = pool[:r.randint(1, 3)]
    if mentioned and biz.get("website") and r.random() < (0.7 if fixed_keys else 0.35):  # fixes publish to your site
        read.insert(0, domain_of(biz["website"]))
    if (wrong and r.random() < 0.7) or r.random() < 0.08:  # otherwise a wrong claim has no source: made up
        read.append(DEMO_STALE[seg])
    good, bad = DESCRIPTORS[seg]
    words = r.sample(good, 2) + ([r.choice(bad)] if wrong and r.random() < 0.5 else [])
    serious = any(by_key[c["fact_key"]]["category"] in {"license", "insurance", "contact"} and
                  c["value"] != by_key[c["fact_key"]]["value"] for c in claims)
    return text, {"mentioned": mentioned, "position": position,
                  "competitors": [n for n in names if n != biz["name"]], "claims": claims,
                  "description": (f"A {biz['category']} known for {words[0]} and {words[1]}."
                                  if mentioned else ""),
                  "descriptors": words if mentioned else [],
                  "sentiment": "negative" if serious else ("positive" if mentioned and not wrong else "neutral"),
                  "sources": [{"url": f"https://{d}", "title": ""} for d in read]}


# ---------------------------------------------------------------- Fix Agent

def _jsonld(biz: dict, fact: dict | None) -> dict:
    data = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": biz["name"],
            "address": {"@type": "PostalAddress", "addressLocality": biz["city"]}}
    if not fact:
        data["knowsLanguage"] = ["en", "es"]
        return data
    cat, v = fact["category"], fact["value"]
    if biz.get("segment") == "trades":
        data["@type"] = "HomeAndConstructionBusiness"
    if is_shop(biz):
        data["@type"] = "OnlineStore"
        data.pop("address", None)
        data["url"] = biz.get("website") or ""
    if fact.get("product"):
        offer = {"@type": "Offer", "priceCurrency": "USD"}
        if cat == "price":
            offer["price"] = v
        if cat == "stock":
            out = "out" in v.lower()
            offer["availability"] = "https://schema.org/" + ("OutOfStock" if out else "InStock")
        product = {"@context": "https://schema.org", "@type": "Product", "name": fact["product"],
                   "brand": {"@type": "Brand", "name": biz["name"]}, "offers": offer}
        if cat in {"spec", "feature"}:
            product["additionalProperty"] = {"@type": "PropertyValue", "name": fact["label"], "value": v}
        return product
    if cat == "license":
        data["hasCredential"] = {"@type": "EducationalOccupationalCredential", "credentialCategory": "license",
                                 "identifier": v}
        return data
    if cat == "service_area":
        data["areaServed"] = [{"@type": "City", "name": c.strip()} for c in v.split(",") if c.strip()]
        return data
    if cat == "warranty":
        data["makesOffer"] = {"@type": "Offer", "warranty": {
            "@type": "WarrantyPromise", "durationOfWarranty": {
                "@type": "QuantitativeValue", "value": 0 if v in {"none", "0"} else v, "unitCode": "MON"}}}
        return data
    if cat == "shipping":
        lo, _, hi = v.partition("-")
        data["makesOffer"] = {"@type": "Offer", "shippingDetails": {
            "@type": "OfferShippingDetails", "deliveryTime": {
                "@type": "ShippingDeliveryTime", "transitTime": {
                    "@type": "QuantitativeValue", "minValue": lo, "maxValue": hi or lo, "unitCode": "DAY"}}}}
        return data
    if cat == "returns":
        data["hasMerchantReturnPolicy"] = {
            "@type": "MerchantReturnPolicy",
            "returnPolicyCategory": "https://schema.org/" + (
                "MerchantReturnNotPermitted" if v in {"none", "0"} else "MerchantReturnFiniteReturnWindow"),
            "merchantReturnDays": 0 if v in {"none", "0"} else v}
        return data
    if cat == "hours":
        day = fact["key"].split(".")[-1].title()
        if v == "closed":
            data["openingHoursSpecification"] = {"@type": "OpeningHoursSpecification", "dayOfWeek": day,
                                                 "opens": "00:00", "closes": "00:00"}
        else:
            o, c = v.split("-")
            data["openingHoursSpecification"] = {"@type": "OpeningHoursSpecification", "dayOfWeek": day,
                                                 "opens": o, "closes": c}
    elif cat == "price":
        data["makesOffer"] = {"@type": "Offer", "name": fact["label"], "price": v, "priceCurrency": "USD"}
    elif cat == "contact":
        data["telephone"] = v
    elif cat == "language":
        data["knowsLanguage"] = ["en", "es"]
    elif cat == "service":
        data["makesOffer"] = {"@type": "Offer", "itemOffered": {"@type": "Service", "name": fact["label"]}}
    return data


def template_fix(inc: dict, biz: dict, fact: dict | None) -> dict:
    who = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini", "perplexity": "Perplexity"}.get(
        inc.get("provider") or "", "AI assistants")
    if inc["type"] == "missed_opportunity":
        need, lang = inc["category"], "Spanish" if inc["language"] == "es" else "English"
        return {
            "explanation_en": f"When customers ask about “{need}” in {lang}, AI assistants usually recommend "
                              f"other businesses. {inc['detail']} Your website doesn't clearly say you offer this, "
                              f"so AI has little to go on.",
            "explanation_es": f"Cuando los clientes preguntan por “{need}” en "
                              f"{'español' if inc['language']=='es' else 'inglés'}, la IA suele recomendar otros "
                              f"negocios. Tu sitio web no dice claramente que ofreces esto.",
            "website_text_en": (f"Shop {need.lower()} at {biz['name']}: certified refurbished, full spec sheet, "
                                f"warranty included. Se habla español." if biz.get("segment") == "tech" else
                                f"Shop {need.lower()} at {biz['name']}: handmade, ships nationwide, easy returns. "
                                f"Se habla español." if biz.get("segment") == "ecommerce" else
                                f"Looking for {need.lower()} in {biz['city']}? {biz['name']} can help. "
                                f"Call us or stop by. Se habla español."),
            "website_text_es": (f"Compra {need.lower()} en {biz['name']}: reacondicionado certificado, "
                                f"especificaciones completas y garantía incluida. We speak English too."
                                if biz.get("segment") == "tech" else
                                f"Compra {need.lower()} en {biz['name']}: hecho a mano, envíos a todo el país. "
                                f"We speak English too." if biz.get("segment") == "ecommerce" else
                                f"¿Buscas {need.lower()} en {biz['city']}? En {biz['name']} te ayudamos. "
                                f"Llámanos o visítanos. We speak English too."),
            "jsonld": _jsonld(biz, fact),
            "action": "Add a bilingual FAQ section to your website and Google Business Profile.",
        }
    label, truth, ai = fact_name(fact), inc["verified_value"], inc["ai_value"]
    label_es = fact_name(fact, "es")
    if inc["type"] == "source_conflict":
        site = inc.get("provider") or "a listing"
        return {
            "explanation_en": f"{site} shows your {label.lower()} as “{display_value(fact, ai)}”, but the verified value is "
                              f"“{display_value(fact, truth)}”. AI assistants read this page, so they may repeat it.",
            "explanation_es": f"{site} muestra tu {label_es.lower()} como “{display_value(fact, ai, 'es')}”, pero el dato "
                              f"verificado es “{display_value(fact, truth, 'es')}”. Los asistentes de IA leen esta página y "
                              f"pueden repetirlo.",
            "website_text_en": f"{label[:1].upper() + label[1:]}: {display_value(fact, truth)}",
            "website_text_es": f"{label_es[:1].upper() + label_es[1:]}: {display_value(fact, truth, 'es')}",
            "jsonld": _jsonld(biz, fact),
            "action": f"Claim or log in to your listing on {site} and correct it. If you can't, ask the site to update or "
                      f"remove it. Then we re-check the page on the next scan.",
        }
    if fact["category"] == "contact":
        return {
            "explanation_en": f"{who} is giving customers the wrong phone number ({ai}). Your verified number is "
                              f"{truth}. Calls may go to a competitor or a scam line.",
            "explanation_es": f"{who} está dando un número de teléfono incorrecto ({ai}). Tu número verificado es "
                              f"{truth}. Las llamadas podrían ir a otro negocio o a una estafa.",
            "website_text_en": f"Call {biz['name']}: {truth}",
            "website_text_es": f"Llama a {biz['name']}: {truth}",
            "jsonld": _jsonld(biz, fact),
            "action": "Check directory listings for the wrong number, correct them, and report the answer "
                      "through the assistant's feedback button. Escalate to consultant today.",
        }
    shop = is_shop(biz)
    ai_en, truth_en = display_value(fact, ai), display_value(fact, truth)
    ai_es, truth_es = display_value(fact, ai, "es"), display_value(fact, truth, "es")
    return {
        "explanation_en": f"{who} shows your {label.lower()} as “{ai_en}”, but your verified value is “{truth_en}”. "
                          + ("Shoppers may buy elsewhere, or order expecting something different and return it."
                             if shop else
                             "Customers may choose someone else or arrive expecting something different."),
        "explanation_es": f"{who} muestra tu {label_es.lower()} como “{ai_es}”, pero el dato verificado es "
                          f"“{truth_es}”. "
                          + ("Los compradores podrían irse a otra tienda, o comprar esperando algo distinto y "
                             "devolverlo." if shop else
                             "Los clientes podrían ir a otro lugar o llegar con expectativas equivocadas."),
        "website_text_en": f"{label[:1].upper() + label[1:]}: {truth_en}",
        "website_text_es": f"{label_es[:1].upper() + label_es[1:]}: {truth_es}",
        "jsonld": _jsonld(biz, fact),
        "action": ("Show the license number and insurance on your website, Google Business Profile, Angi, Yelp and "
                   "Nextdoor, and link to the official license lookup so AI can verify it. Escalate today."
                   if fact["category"] in {"license", "insurance"} else
                   "Update the spec table on the product page and every marketplace listing (Amazon, eBay, "
                   "Back Market) so they match the manufacturer spec sheet, then add this structured data."
                   if biz.get("segment") == "tech" and fact["category"] in {"spec", "feature"} else
                   "Update the product page and your store feed (Shopify, eBay) so every channel shows the same "
                   "value, then add this structured data to the product page."
                   if shop else
                   "Make this fact clear on your website, then update Google Business Profile and Yelp to match."),
    }


def generate_fix(inc: dict, biz: dict, fact: dict | None) -> dict:
    draft = template_fix(inc, biz, fact)
    if is_demo():
        return draft
    prompt = f"""You help a small business fix how AI assistants describe it.
Business: {biz['name']}, a {biz['category']} in {biz['city']}.
Issue: {json.dumps({k: inc[k] for k in ('type','provider','category','language','ai_value','verified_value','detail')})}
Improve this draft for a non-technical owner. Plain language, no jargon. Never invent facts,
prices or promises beyond the verified value. Return ONLY JSON with the same keys:
{json.dumps(draft, ensure_ascii=False)}"""
    try:
        improved = parse_json(_utility(prompt))
        improved["jsonld"] = draft["jsonld"]  # structured data stays deterministic
        return improved
    except Exception:
        return draft
