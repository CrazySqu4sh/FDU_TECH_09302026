"""Website check: read a business's site the way an AI assistant would, and say what to improve.

Fetches the homepage, robots.txt and a few key pages (services, prices, about, contact, FAQ, Spanish), then:
  - discovers the facts AI can learn from the site (phone, prices, hours, services, area, trust, Spanish)
  - scores AI-readiness with 12 checks, each with a plain-language recommendation
  - writes ready-to-paste fixes: structured data (JSON-LD) and a bilingual Q&A block
  - optionally compares a service/product list (CSV) or the business's verified facts against the site

Plain code, no AI, no API key, $0. Real sites are fetched live; demo '.example' sites are simulated.
"""
import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import agents, reader
from .validator import values_match

UA = "Mozilla/5.0 (compatible; AapareceSiteCheck/1.0; checks how AI assistants read this site)"
MAX_PAGES = 6
LINK_HINTS = re.compile(r"servic|pric|precio|rate|tarifa|about|nosotros|contact|faq|pregunta|area|zona|espa|/es\b|booking|reserv",
                        re.I)
SEARCH_BOTS = ["OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Bingbot", "Googlebot"]
TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended"]
SERVICE_WORDS = {
    "cleaning": [("Deep cleaning", "limpieza profunda", r"deep\s*clean|limpieza profunda"),
                 ("Move-out cleaning", "limpieza de mudanza", r"move[\s-]*(out|in)|mudanza"),
                 ("Office cleaning", "limpieza de oficinas", r"office|commercial|oficina|comercial"),
                 ("Recurring cleaning", "limpieza recurrente", r"weekly|bi-?weekly|recurring|semanal|quincenal"),
                 ("Post-construction cleaning", "limpieza post-construcción", r"post[\s-]*construction|construcci"),
                 ("Airbnb / vacation rental", "limpieza de Airbnb", r"airbnb|vacation rental|short[\s-]term"),
                 ("Window cleaning", "limpieza de ventanas", r"window|ventana"),
                 ("Carpet cleaning", "limpieza de alfombras", r"carpet|alfombra"),
                 ("Eco-friendly products", "productos ecológicos", r"eco[\s-]*friendly|green clean|ecol[oó]gic"),
                 ("Brings own supplies", "trae sus propios productos", r"(bring|provide)s? (our|their|all)? ?(own )?supplies|productos incluidos")],
    "trades": [("Roof repair", "reparación de techos", r"roof|techo"), ("Remodeling", "remodelación", r"remodel"),
               ("Free estimates", "estimados gratis", r"free (estimate|quote)|estimado gratis|cotizaci[oó]n gratis"),
               ("Emergency service", "servicio de emergencia", r"emergenc|24/7|24 hour"),
               ("Gutters", "canaletas", r"gutter|canalet")],
}
TRUST = [("insured", r"insured|bonded|asegurad|con seguro|fianza"), ("licensed", r"licen[cs]ed|licencia"),
         ("background", r"background[\s-]*check|antecedentes"), ("guarantee", r"guarantee|garant[ií]a|satisfaction")]
STATES = ("AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|"
          "OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC")
CITY = re.compile(rf"\b([A-Z][a-zA-Z.]+(?: [A-Z][a-zA-Z.]+){{0,2}}),\s?({STATES})\b")
SEGMENT_HINTS = {  # guess the business type from the site's own words
    "cleaning": r"\bclean|maid|janitorial|housekeep|limpieza",
    "trades": r"\broof|remodel|plumb|hvac|contractor|landscap|painting|electrician|handyman|techo",
    "tech": r"\blaptop|refurbish|phone repair|iphone|computer repair",
    "ecommerce": r"add to cart|shop now|free shipping|checkout",
}
ES_WORDS = re.compile(r"\b(limpieza|servicio|nuestro|llámenos|llamenos|cotización|preguntas|hablamos|se habla|español|precios|horario)\b", re.I)


# ------------------------------------------------------------ fetching

def normalize(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url.rstrip("/")


MARKETPLACES = ("ebay.", "etsy.", "amazon.", "walmart.", "facebook.", "instagram.", "yelp.", "thumbtack.", "angi.")


def _get(url: str) -> tuple[int, str]:
    # We identify ourselves honestly and never try to get around a site's bot protection.
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/plain,*/*",
                                               "Accept-Language": "en-US,en;q=0.9,es;q=0.8", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read(3_000_000)
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return r.status, body[:1_500_000].decode(r.headers.get_content_charset() or "utf-8", "replace")


def error_kind(e: Exception) -> str:
    """blocked (the site refuses automated readers), not_found, or unreachable (bad address, down, timeout)."""
    code = getattr(e, "code", None)
    if code in (401, 403, 429, 503, 999):
        return "blocked"
    if code in (404, 410):
        return "not_found"
    return "unreachable"


def crawl(url: str) -> dict:
    """Homepage + robots.txt + up to 5 key internal pages."""
    base = normalize(url)
    host = urllib.parse.urlparse(base).netloc
    out = {"url": base, "pages": [], "robots": "", "errors": [], "error_kind": None,
           "marketplace": any(m in host for m in MARKETPLACES)}
    try:
        status, home = _get(base)
    except Exception as e:
        out["error_kind"] = error_kind(e)
        out["errors"].append(f"{getattr(e, 'code', '') or type(e).__name__}")
        return out
    out["pages"].append({"url": base, "html": home})
    try:
        out["robots"] = _get(f"{urllib.parse.urlparse(base).scheme}://{host}/robots.txt")[1]
    except Exception:
        out["robots"] = ""
    links = []
    for href, text in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', home, re.S | re.I):
        full = urllib.parse.urljoin(base + "/", href)
        if urllib.parse.urlparse(full).netloc == host and (LINK_HINTS.search(href) or LINK_HINTS.search(text)):
            links.append(full.split("?")[0].rstrip("/"))
    for link in list(dict.fromkeys(l for l in links if l != base))[:MAX_PAGES - 1]:
        try:
            out["pages"].append({"url": link, "html": _get(link)[1]})
        except Exception as e:
            out["errors"].append(f"{link}: {type(e).__name__}")
    return out


def demo_crawl(url: str, db) -> dict | None:
    """Demo '.example' sites: the business's current (weak) page, like the Proof Lab's 'before' version."""
    from . import prooflab
    from .services import load_business, load_facts
    domain = agents.domain_of(url)
    b = db.execute("SELECT id FROM businesses WHERE website LIKE ?", (f"%{domain}%",)).fetchone()
    if not b:
        return None
    biz, facts = load_business(db, b[0]), load_facts(db, b[0])
    text = prooflab.pages(biz, facts, "before")[biz["name"]]
    html = "<html lang='en'><head><title>" + biz["name"] + "</title></head><body>" + \
        "".join(f"<p>{line}</p>" for line in text.splitlines()) + "</body></html>"
    return {"url": normalize(url), "pages": [{"url": normalize(url), "html": html}], "robots": "", "errors": [],
            "simulated": True}


# ------------------------------------------------------------ reading

def robots_blocked(robots: str, bot: str) -> bool:
    """True if robots.txt disallows the whole site for this bot (its own group, or '*' when it has none)."""
    groups, cur, agents_ = {}, [], False
    for line in robots.splitlines():
        line = line.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if not agents_:
                cur = []
            cur.append(v.lower())
            agents_ = True
            for a in cur:
                groups.setdefault(a, [])
        elif k in ("disallow", "allow"):
            agents_ = False
            for a in cur:
                groups.setdefault(a, []).append((k, v))
    rules = groups.get(bot.lower(), groups.get("*", []))
    return any(k == "disallow" and v == "/" for k, v in rules) and not any(k == "allow" and v == "/" for k, v in rules)


def _meta(html: str, name: str) -> str:
    m = re.search(rf'<meta[^>]+(?:name|property)=["\']{name}["\'][^>]+content=["\']([^"\']*)', html, re.I) or \
        re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{name}["\']', html, re.I)
    return m.group(1).strip() if m else ""


def discover(site: dict, segment: str) -> dict:
    htmls = [p["html"] for p in site["pages"]]
    texts, blocks = [], []
    for h in htmls:
        t, b = reader.html_to_text(h)
        texts.append(t)
        blocks += b
    text = "\n".join(texts)
    home = htmls[0] if htmls else ""
    title = re.search(r"<title[^>]*>(.*?)</title>", home, re.S | re.I)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", home, re.S | re.I)
    types = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type")
            types.extend(t if isinstance(t, list) else [t] if t else [])
            for v in o.values():
                walk(v)
    walk(blocks)
    ld = json.dumps(blocks).lower()
    prices = []
    for line in text.splitlines():
        for m in reader.PRICE.finditer(line):
            label = re.sub(r"[:\-–|$].*$", "", line[:m.start()]).strip(" :-–|")[:60] or "Price"
            prices.append({"label": label, "value": m.group(1).replace(",", "")})
    hours = [line.strip()[:80] for line in text.splitlines()
             if re.search(r"\b(mon|tue|wed|thu|fri|sat|sun|lunes|s[aá]bado|domingo)", line, re.I)
             and (reader.HOURS.search(line) or reader.CLOSED.search(line))][:7]
    area = re.search(r"(?:serving|service areas?|areas we serve|we serve|zona de servicio|servimos)[:\s]+([^\n.]{3,160})",
                     text, re.I)
    if area and not re.search(r",| and | y |\b(" + STATES + r")\b", area.group(1)):
        area = None  # "Serving Mexico City street food" is a slogan, not a service area; a real area lists places
    words = SERVICE_WORDS.get(segment) or [w for v in SERVICE_WORDS.values() for w in v]
    services = [{"label": en, "label_es": es} for en, es, rx in words if re.search(rx, text, re.I)]
    # Who and where: structured data first, then the page's own title / text.
    name = ""
    for b in blocks if isinstance(blocks, list) else []:
        for o in (b if isinstance(b, list) else [b]):
            if isinstance(o, dict) and o.get("name") and o.get("@type") not in ("WebPage", "WebSite", "BreadcrumbList"):
                name = str(o["name"]).strip()
                break
        if name:
            break
    name = name or _meta(home, "og:site_name") or (re.split(r"\s[|\-–—:]\s", re.sub(r"\s+", " ", title.group(1)).strip())[0]
                                                   if title else "")
    loc = re.search(r'"addresslocality"\s*:\s*"([^"]+)".{0,200}?"addressregion"\s*:\s*"([^"]+)"', ld)
    city_m = CITY.search(text)
    city = f"{loc.group(1).title()}, {loc.group(2).upper()}" if loc else (f"{city_m.group(1)}, {city_m.group(2)}" if city_m else "")
    scores = {seg: len(re.findall(rx, text, re.I)) for seg, rx in SEGMENT_HINTS.items()}
    guess = max(scores, key=scores.get) if max(scores.values()) >= 3 else "services"
    lang_es = bool(re.search(r'hreflang=["\']es|lang=["\']es', " ".join(htmls), re.I)) or len(ES_WORDS.findall(text)) >= 6
    return {
        "name": name[:80], "city": city, "segment_guess": guess,
        "text": text, "pages_read": [p["url"] for p in site["pages"]],
        "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
        "description": _meta(home, "description") or _meta(home, "og:description"),
        "h1": re.sub(r"<[^>]+>|\s+", " ", h1.group(1)).strip() if h1 else "",
        "phones": list(dict.fromkeys(m.group(0) for m in reader.PHONE.finditer(text)))[:3],
        "prices": prices[:12], "hours": hours, "area": area.group(1).strip() if area else "",
        "services": services, "trust": [k for k, rx in TRUST if re.search(rx, text, re.I)],
        "spanish": lang_es, "faq": bool(re.search(r"\bfaq\b|frequently asked|preguntas frecuentes", text, re.I))
        or "faqpage" in ld,
        "reviews": bool(re.search(r"\breviews?\b|reseñas|\bstars?\b|★", text, re.I)),
        "jsonld_types": [t for t in dict.fromkeys(types) if t],
        "jsonld_fields": {f: f.lower() in ld for f in ("telephone", "address", "areaServed", "openingHours", "priceRange")},
    }


# ------------------------------------------------------------ scoring

def checks(d: dict, site: dict, name: str, city: str) -> list[dict]:
    blocked = [b for b in SEARCH_BOTS if robots_blocked(site["robots"], b)]
    local = any(t for t in d["jsonld_types"] if t in {"LocalBusiness", "HomeAndConstructionBusiness", "ProfessionalService",
                                                        "HousePainter", "Plumber", "Organization", "Store", "Restaurant"})
    city_word = (city or "").split(",")[0].strip().lower()
    head = f"{d['title']} {d['description']} {d['h1']}".lower()
    c = [
        ("crawlers", 12, not blocked, {"blocked": blocked}),
        ("structured_data", 12, local and sum(d["jsonld_fields"].values()) >= 2, {"types": d["jsonld_types"]}),
        ("phone", 8, bool(d["phones"]), {"found": d["phones"]}),
        ("hours", 8, bool(d["hours"]), {"found": d["hours"][:3]}),
        ("prices", 10, bool(d["prices"]), {"found": d["prices"][:4]}),
        ("services", 10, len(d["services"]) >= 3, {"found": [s["label"] for s in d["services"]]}),
        ("area", 8, bool(d["area"]), {"found": d["area"]}),
        ("trust", 8, "insured" in d["trust"] or "licensed" in d["trust"], {"found": d["trust"]}),
        ("spanish", 8, d["spanish"], {}),
        ("faq", 6, d["faq"], {}),
        ("headline", 5, bool(city_word) and city_word in head and bool(d["description"]), {"title": d["title"],
                                                                                         "description": d["description"]}),
        ("reviews", 5, d["reviews"], {}),
    ]
    return [{"id": i, "weight": w, "pass": bool(p), "detail": det} for i, w, p, det in c]


def fixes(d: dict, name: str, city: str, url: str, segment: str, items: list | None = None,
          facts: list | None = None) -> dict:
    """Ready-to-paste fixes built from the TRUE values: verified facts first, then the owner's list, then the site.
    Services the site is missing are added. Anything unknown is left as a clear [placeholder]."""
    facts, items = facts or [], [i for i in (items or []) if i.get("name")]
    by_cat = lambda c: [f for f in facts if f["category"] == c]  # noqa: E731
    phone = (by_cat("contact") or [{"value": None}])[0]["value"] or (d["phones"][0] if d["phones"] else "[your phone]")
    area = (by_cat("service_area") or [{"value": None}])[0]["value"] or d["area"] or \
        (city.split(",")[0].strip() if city else "[cities you serve]")
    if by_cat("price"):
        prices = [{"label": f["label"], "label_es": f.get("label_es") or "", "value": f["value"]} for f in by_cat("price")]
    elif any(i.get("price") for i in items):
        prices = [{"label": i["name"], "label_es": i.get("name_es") or "", "value": i["price"]} for i in items if i.get("price")]
    else:
        prices = d["prices"]
    services = [f["label"] for f in by_cat("service") if f["value"] == "yes"] or [i["name"] for i in items]
    services = list(dict.fromkeys(services + [x["label"] for x in d["services"]]))
    insured = any(f["value"] == "yes" for f in by_cat("insurance")) or "insured" in d["trust"]
    ld = {"@context": "https://schema.org", "@type": "HomeAndConstructionBusiness" if segment == "trades" else "LocalBusiness",
          "name": name or "[business name]", "url": url, "telephone": phone,
          "areaServed": [a.strip() for a in re.split(r",| and | y ", area) if a.strip()][:8], "knowsLanguage": ["en", "es"]}
    hours = [f"{f['key'].split('.')[-1].title()[:2]} {f['value']}" for f in by_cat("hours") if f["value"] != "closed"] or d["hours"][:7]
    if hours:
        ld["openingHours"] = hours
    if services or prices:
        ld["makesOffer"] = [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": sv}} for sv in services[:8]] + \
                           [{"@type": "Offer", "name": p["label"], "price": p["value"], "priceCurrency": "USD"} for p in prices[:4]]
    price = prices[0] if prices else {"label": "[main service]", "value": "[price]"}
    pl = price["label"].lower()
    faq_en = [f"Where do you work? We serve {area}.",
              f"How much does {pl} cost? From ${price['value']}.",
              f"What services do you offer? {', '.join(services[:5]) or '[your services]'}.",
              f"Are you insured? {'Yes, we are fully insured.' if insured else '[Yes/No: add your insurance details]'}",
              f"How do I book? Call {phone}. Se habla español."]
    faq_es = [f"¿Dónde trabajan? Damos servicio en {area}.",
              f"¿Cuánto cuesta {(price.get('label_es') or price['label']).lower()}? Desde ${price['value']}.",
              f"¿Qué servicios ofrecen? {', '.join(services[:5]) or '[tus servicios]'}.",
              f"¿Tienen seguro? {'Sí, estamos asegurados.' if insured else '[Sí/No: agrega los datos de tu seguro]'}",
              f"¿Cómo reservo? Llama al {phone}. We speak English too."]
    main = services[0] if services else "[Main service]"
    return {"jsonld": ld, "faq_en": faq_en, "faq_es": faq_es,
            "title": f"{name or '[Business name]'} | {main} in {city.split(',')[0] if city else '[City]'}",
            "description": f"{name or '[Business name]'} offers {', '.join(sv.lower() for sv in services[:3]) or '[your services]'} "
                           f"in {area}. {'Insured. ' if insured else ''}Call {phone}. Se habla español.",
            "source": "verified facts" if facts else "your list" if items else "your website"}


def compare_items(d: dict, items: list[dict]) -> list[dict]:
    """Each item from the owner's list: is it on the site, with the same price, and in Spanish?"""
    low = reader.fold(d["text"])
    out = []
    for it in items[:60]:
        nm = (it.get("name") or "").strip()
        if not nm:
            continue
        words = [w for w in re.findall(r"[a-z0-9]+", reader.fold(nm)) if len(w) > 3][:3] or [reader.fold(nm)]
        on_site = all(w in low for w in words)
        price_ok = None
        if it.get("price") and on_site:
            fact = {"category": "price", "value": str(it["price"]).replace("$", ""), "label": nm, "label_es": it.get("name_es", ""), "key": "x"}
            found = reader.candidates(d["text"], fact, anywhere=False)
            price_ok = any(values_match(fact, v) for v, _ in found) if found else None
        es = it.get("name_es", "").strip()
        out.append({"name": nm, "name_es": es, "price": it.get("price") or "", "on_site": on_site, "price_matches": price_ok,
                    "spanish_on_site": bool(es) and reader.fold(es) in low})
    return out


def compare_facts(d: dict, facts: list[dict]) -> list[dict]:
    """The business's verified facts vs. what its own website says."""
    out = []
    for f in facts:
        if f["category"] in {"language", "feature"}:
            continue
        cands = reader.candidates(d["text"], f, anywhere=f["category"] != "price")
        found = cands[0][0] if cands else None
        out.append({"key": f["key"], "label": f["label"], "category": f["category"], "value": f["value"], "found": found,
                    "status": "missing" if found is None else "match" if values_match(f, found) else "different"})
    return out


def audit(db, url: str, name: str = "", city: str = "", segment: str = "cleaning", items: list | None = None,
          business_id: int | None = None) -> dict:
    site = demo_crawl(url, db) if agents.domain_of(normalize(url)).endswith(".example") else crawl(url)
    if site is None or not site["pages"]:
        return {"ok": False, "url": normalize(url), "errors": (site or {}).get("errors") or ["This demo address doesn't exist."],
                "error_kind": (site or {}).get("error_kind") or "not_found",
                "marketplace": bool((site or {}).get("marketplace")), "business": {"name": name, "city": city, "segment": segment}}
    d = discover(site, segment)
    if not segment:  # quick scan: let the site say what kind of business it is, then read services for that type
        segment = d["segment_guess"]
        d = discover(site, segment)
    name, city = name or d["name"], city or d["city"]
    cs = checks(d, site, name, city)
    score = sum(c["weight"] for c in cs if c["pass"])
    res = {"ok": True, "url": site["url"], "business": {"name": name, "city": city, "segment": segment}, "found_name": d["name"], "simulated": bool(site.get("simulated")), "errors": site["errors"],
           "pages_read": d["pages_read"], "score": score, "checks": cs,
           "found": {k: d[k] for k in ("title", "description", "phones", "prices", "hours", "area", "services", "trust",
                                       "spanish", "faq", "jsonld_types")},
           "fixes": None,
           "items": compare_items(d, items or []),
           "training_bots_blocked": [b for b in TRAINING_BOTS if robots_blocked(site["robots"], b)]}
    facts = []
    if business_id:
        from .services import load_facts
        facts = load_facts(db, business_id)
        res["facts"] = compare_facts(d, facts)
    res["fixes"] = fixes(d, name, city, site["url"], segment, items, facts)
    # Facts we can suggest for the verified profile, straight from the owner's own site.
    sug = []
    if d["phones"]:
        sug.append({"key": "contact.phone", "label": "Phone number", "label_es": "teléfono", "value": d["phones"][0], "category": "contact"})
    for p in d["prices"][:4]:
        sug.append({"label": p["label"], "label_es": "", "value": p["value"], "category": "price"})
    if d["area"]:
        sug.append({"key": "area.service", "label": "Service area", "label_es": "zona de servicio", "value": d["area"], "category": "service_area"})
    if "insured" in d["trust"]:
        sug.append({"key": "credential.insurance", "label": "Insured", "label_es": "con seguro", "value": "yes", "category": "insurance"})
    for s in d["services"][:6]:
        sug.append({"label": s["label"], "label_es": s["label_es"], "value": "yes", "category": "service"})
    res["suggested_facts"] = [{**f, "evidence": "document", "source": f"Website ({agents.domain_of(site['url'])})"} for f in sug]
    return res
