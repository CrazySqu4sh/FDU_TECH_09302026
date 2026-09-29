"""The AI agents. Each has one narrow job.

Live mode calls real assistants (Claude, ChatGPT) when API keys are set.
Demo mode simulates assistant answers so the full workflow runs with no keys.
Set DEMO_MODE=true|false|auto (auto = demo only when no keys are present).
"""
import hashlib
import json
import os
import random
import re

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DEMO_MODE = os.getenv("DEMO_MODE", "auto").lower()

CLAUDE_ASSISTANT_MODEL = os.getenv("CLAUDE_ASSISTANT_MODEL", "claude-sonnet-5-5")
CLAUDE_UTILITY_MODEL = os.getenv("CLAUDE_UTILITY_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_WEB_TOOL = os.getenv("OPENAI_WEB_TOOL", "web_search")
MAX_JOURNEYS = int(os.getenv("MAX_JOURNEYS", "12"))

DEMO_PROVIDERS = ["chatgpt", "claude", "gemini", "perplexity"]
DAYS_ES = {"monday": "lunes", "tuesday": "martes", "wednesday": "miércoles", "thursday": "jueves",
           "friday": "viernes", "saturday": "sábado", "sunday": "domingo"}


def live_providers() -> list[str]:
    out = []
    if OPENAI_KEY:
        out.append("chatgpt")
    if ANTHROPIC_KEY:
        out.append("claude")
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


def _openai(prompt: str, web: bool = False) -> str:
    from openai import OpenAI
    client = OpenAI()
    kwargs = dict(model=OPENAI_MODEL, input=prompt)
    if web:
        kwargs["tools"] = [{"type": OPENAI_WEB_TOOL}]
    return client.responses.create(**kwargs).output_text


def _utility(prompt: str) -> str:
    """Cheap model for extraction and drafting."""
    if ANTHROPIC_KEY:
        return _claude(prompt, CLAUDE_UTILITY_MODEL)
    return _openai(prompt)


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
    if lang == "es":
        product = fact.get("product_es") or product
        return f"{label.lower()} de {product}" if product else label
    return f"{product} {label.lower()}" if product else label


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
    return value


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


def generate_journeys(biz: dict, facts: list[dict]) -> list[dict]:
    if is_demo():
        if biz.get("segment") == "ecommerce":
            return ecommerce_journeys(biz, facts)
        return template_journeys(biz, facts)
    keys = [f["key"] for f in facts]
    kind = ("an online store (e-commerce) that ships products" if biz.get("segment") == "ecommerce"
            else "a local service business")
    prompt = f"""You write realistic questions shoppers ask AI assistants.
Business type: {biz['category']}, {kind}, based in {biz['city']}.
Its verified facts (keys): {keys}
Write {MAX_JOURNEYS} questions: half in English, half in natural U.S. Spanish (Spanglish is fine).
Cover different customer needs (price, specific products or services, availability, shipping,
returns, hours, specialties, language). Use a product's name as the category for product questions.
Never mention the business name. Return ONLY a JSON array of objects:
{{"question": str, "language": "en"|"es", "category": short need label in English,
 "related_facts": [fact keys from the list that the question is about]}}"""
    try:
        return parse_json(_utility(prompt))[:MAX_JOURNEYS]
    except Exception:
        return ecommerce_journeys(biz, facts) if biz.get("segment") == "ecommerce" else template_journeys(biz, facts)


# -------------------------------------------------------- Query Runner (live)

def ask_assistant(provider: str, question: str, city: str) -> str:
    # APIs have no GPS location, so we state the city the way a local user's app would.
    prompt = f"{question}\n\n(I'm located in {city}.)" if city else question
    if provider == "claude":
        return _claude(prompt, CLAUDE_ASSISTANT_MODEL, web=True)
    if provider == "chatgpt":
        return _openai(prompt, web=True)
    raise ValueError(f"Unsupported provider {provider}")


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
 "claims": [{{"fact_key": key from the list, "value": value in the required format}}]}}
Only include claims the answer makes about "{biz['name']}" itself. Do not guess.

Answer:
\"\"\"{answer}\"\"\""""
    try:
        data = parse_json(_utility(prompt))
        return {"mentioned": bool(data.get("mentioned")), "position": data.get("position"),
                "competitors": data.get("competitors", []), "claims": data.get("claims", [])}
    except Exception:
        mentioned = biz["name"].lower() in answer.lower()
        return {"mentioned": mentioned, "position": None,
                "competitors": [c for c in competitors if c.lower() in answer.lower()], "claims": []}


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
    if cat == "contact":
        digits = re.sub(r"\D", "", v)
        return f"({digits[:3]}) {digits[3:6]}-0199" if len(digits) >= 10 else None
    return None


def _phrase(fact: dict, value: str, lang: str) -> str:
    cat = fact["category"]
    label = fact["label"] if lang == "en" else (fact.get("label_es") or fact["label"])
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


FILLER_EN = ["well reviewed for honest pricing", "popular with locals", "known for quick turnaround",
             "strong reviews for customer service"]
FILLER_ES = ["con buenas reseñas por precios justos", "muy popular en la zona", "conocido por su rapidez",
             "buenas opiniones sobre el servicio"]
SHOP_FILLER_EN = ["fast shipping and good reviews", "wide selection", "known for quality craftsmanship",
                  "strong reviews for customer service"]
SHOP_FILLER_ES = ["envíos rápidos y buenas reseñas", "gran variedad", "conocida por su calidad artesanal",
                  "buenas opiniones sobre el servicio"]


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
            shop = biz.get("segment") == "ecommerce"
            pool = (SHOP_FILLER_EN if lang == "en" else SHOP_FILLER_ES) if shop else (
                FILLER_EN if lang == "en" else FILLER_ES)
            detail = r.choice(pool)
        lines.append(f"{i}. {name}: {detail}.")
    if biz.get("segment") == "ecommerce":
        intro = "Here are some good places to shop online:" if lang == "en" else "Estas tiendas en línea son buenas opciones:"
        outro = ("Prices and stock change often, so confirm on the store's site." if lang == "en"
                 else "Los precios y el inventario cambian, confirma en la tienda.")
    else:
        intro = (f"Here are a few options in {biz['city']}:" if lang == "en"
                 else f"Aquí tienes algunas opciones en {biz['city']}:")
        outro = ("Check current hours before visiting." if lang == "en"
                 else "Confirma el horario antes de ir.")
    text = "\n".join([intro, *lines, outro])
    return text, {"mentioned": mentioned, "position": position,
                  "competitors": [n for n in names if n != biz["name"]], "claims": claims}


# ---------------------------------------------------------------- Fix Agent

def _jsonld(biz: dict, fact: dict | None) -> dict:
    data = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": biz["name"],
            "address": {"@type": "PostalAddress", "addressLocality": biz["city"]}}
    if not fact:
        data["knowsLanguage"] = ["en", "es"]
        return data
    cat, v = fact["category"], fact["value"]
    if biz.get("segment") == "ecommerce":
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
        return {"@context": "https://schema.org", "@type": "Product", "name": fact["product"],
                "brand": {"@type": "Brand", "name": biz["name"]}, "offers": offer}
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
            "website_text_en": (f"Shop {need.lower()} at {biz['name']}: handmade, ships nationwide, easy returns. "
                                f"Se habla español." if biz.get("segment") == "ecommerce" else
                                f"Looking for {need.lower()} in {biz['city']}? {biz['name']} can help. "
                                f"Call us or stop by. Se habla español."),
            "website_text_es": (f"Compra {need.lower()} en {biz['name']}: hecho a mano, envíos a todo el país. "
                                f"We speak English too." if biz.get("segment") == "ecommerce" else
                                f"¿Buscas {need.lower()} en {biz['city']}? En {biz['name']} te ayudamos. "
                                f"Llámanos o visítanos. We speak English too."),
            "jsonld": _jsonld(biz, fact),
            "action": "Add a bilingual FAQ section to your website and Google Business Profile.",
        }
    label, truth, ai = fact_name(fact), inc["verified_value"], inc["ai_value"]
    label_es = fact_name(fact, "es")
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
    shop = biz.get("segment") == "ecommerce"
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
        "action": ("Update the product page and your store feed (Shopify, eBay) so every channel shows the same "
                   "value, then add this structured data to the product page."
                   if biz.get("segment") == "ecommerce" else
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
