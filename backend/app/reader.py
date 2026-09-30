"""Reads facts out of plain text with code, no AI: web pages, pasted AI answers, Proof Lab answers.

Used to (1) confirm a business's facts on the pages that list it, (2) check whether a page an assistant
cited actually says what the assistant claimed, and (3) read answers pasted from free AI apps at $0.
It only reports what it can find unambiguously; anything else is left for a person.
"""
import html
import json
import re
import unicodedata

from .validator import values_match

PHONE = re.compile(r"\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}\b")
PRICE = re.compile(r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)")
TIME = r"\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?"
HOURS = re.compile(rf"({TIME})\s*(?:-|–|—|to|a)\s*({TIME})", re.I)
NO_INS = re.compile(r"\b(not insured|no insurance|uninsured|no proof of insurance|sin seguro|no (?:est[aá]|tiene) asegurad)", re.I)
YES_INS = re.compile(r"\b(insured|bonded|asegurad[oa]s?|con seguro|con fianza)", re.I)
CLOSED = re.compile(r"\b(closed|cerrado)\b", re.I)
STOP = {"from", "desde", "with", "your", "service", "services", "cleaning", "clean", "hours", "price", "the", "and",
        "for", "per", "(from)", "bedrooms", "number", "team", "staff", "own", "brings", "con", "de", "del", "los", "las"}
DAY_WORDS = {"monday": ["monday", "mon", "lunes"], "tuesday": ["tuesday", "tue", "martes"],
             "wednesday": ["wednesday", "wed", "miércoles"], "thursday": ["thursday", "thu", "jueves"],
             "friday": ["friday", "fri", "viernes"], "saturday": ["saturday", "sat", "sábado", "sabado"],
             "sunday": ["sunday", "sun", "domingo"]}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def html_to_text(raw: str) -> tuple[str, list]:
    """Visible text plus any JSON-LD blocks (structured data a business publishes for machines)."""
    blocks = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw, re.S | re.I):
        try:
            blocks.append(json.loads(m.group(1).strip()))
        except ValueError:
            pass
    raw = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", raw, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip(), blocks


def keywords(fact: dict) -> list[str]:
    """Distinctive words from a fact's label, to find the right price among several on a page."""
    if fact["category"] == "hours":
        return DAY_WORDS.get(fact["key"].split(".")[-1], [])
    words = re.findall(r"[a-záéíóúñ\-]+", (fact["label"] + " " + (fact.get("label_es") or "")).lower())
    return [w for w in words if len(w) > 3 and w not in STOP][:6]


def _near(text: str, kws: list[str], pattern: re.Pattern, window: int = 140) -> list[tuple[str, str]]:
    """Matches of `pattern` within `window` chars after a keyword. Returns (value, snippet)."""
    low, out = text.lower(), []
    for kw in kws:
        for k in re.finditer(re.escape(kw), low):
            seg = text[k.start(): k.start() + window]
            for m in pattern.finditer(seg):
                out.append((m.group(0), seg.strip()[:200]))
    return out


def _snip(text: str, m: re.Match) -> str:
    return text[max(0, m.start() - 70): m.end() + 70].replace("\n", " ").strip()


def candidates(text: str, fact: dict, anywhere: bool = True) -> list[tuple[str, str]]:
    """Every value for this fact's category found in the text, as (value, snippet). Nearest-to-label first."""
    cat = fact["category"]
    kws = keywords(fact)
    if cat == "contact":
        return [(m.group(0), _snip(text, m)) for m in PHONE.finditer(text)]
    if cat == "price":
        near = [(v.replace("$", "").replace(",", "").strip(), s) for v, s in _near(text, kws, PRICE)]
        if near or not anywhere:
            return near
        return [(m.group(1).replace(",", ""), _snip(text, m)) for m in PRICE.finditer(text)]
    if cat == "hours":
        near = _near(text, kws, re.compile(rf"{HOURS.pattern}|\bclosed\b|\bcerrado\b", re.I), 60)
        return [("closed" if CLOSED.search(v) else v, s) for v, s in near]
    if cat == "insurance":
        out = [("no", _snip(text, m)) for m in NO_INS.finditer(text)]
        if not out:
            out = [("yes", _snip(text, m)) for m in YES_INS.finditer(text)]
        return out
    if cat in {"service", "language", "feature"}:
        low = fold(text)
        for kw in kws:
            i = low.find(fold(kw))
            if i >= 0:
                return [("yes", text[max(0, i - 60): i + 80].replace("\n", " ").strip())]
        return []
    if cat == "service_area":
        found = [c.strip() for c in fact["value"].split(",") if c.strip() and fold(c.strip()) in fold(text)]
        return [(", ".join(found), "")] if found else []
    return []


def jsonld_values(blocks: list, fact: dict) -> list[str]:
    """Values a business states in its structured data (the most machine-readable source)."""
    cat, out = fact["category"], []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            if cat == "contact" and o.get("telephone"):
                out.append(str(o["telephone"]))
            if cat == "price" and o.get("price") and fact["label"].split()[0].lower() in json.dumps(o).lower():
                out.append(str(o["price"]))
            for v in o.values():
                walk(v)
    walk(blocks)
    return out


def found_on_page(text: str, blocks: list, fact: dict) -> tuple[str | None, str]:
    """The single value this page states for the fact, preferring structured data. (value, snippet)."""
    ld = jsonld_values(blocks, fact)
    if ld:
        return ld[0], "structured data (JSON-LD)"
    c = candidates(text, fact, anywhere=False)
    return (c[0][0], c[0][1]) if c else (None, "")


def supports(text: str, fact: dict, claimed: str) -> tuple[bool, str]:
    """Does the page say what the assistant claimed? Uses the same comparison rules as the checker."""
    probe = {**fact, "value": str(claimed)}
    for v, snip in candidates(text, fact):
        if values_match(probe, v):
            return True, snip
    return False, ""


# ------------------------------------------------ reading a pasted or lab answer

def business_segment(text: str, name: str) -> tuple[bool, int | None, str]:
    """Is the business named? Its rank in a numbered list? The lines that talk about it."""
    words = [w for w in re.findall(r"[a-z0-9]+", fold(name)) if w not in {"co", "llc", "inc", "the"}]
    probe = " ".join(words[:2])
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if probe and probe in fold(line):
            m = re.match(r"\s*(?:#|\*\*)?\s*(\d+)[.)]", line)
            seg = "\n".join(lines[i: i + 3])
            return True, int(m.group(1)) if m else None, seg
    return (probe in fold(text), None, text) if probe else (False, None, "")


def list_names(text: str) -> list[str]:
    """Business names from a numbered or bulleted list ("1. **Name** – why"), the way assistants answer."""
    names = []
    for line in text.splitlines():
        m = re.match(r"\s*(?:\d+[.)]|[-*•])\s+(.+)", line)
        if not m:
            continue
        item = re.sub(r"[*_#`]", "", m.group(1)).strip()
        name = re.split(r"\s[–—-]\s|:\s|\s\(|,\s", item)[0].strip(" .")
        if 2 < len(name) <= 60 and not name.lower().startswith(("http", "www")):
            names.append(name)
    return list(dict.fromkeys(names))


def read_answer(text: str, biz: dict, facts: list[dict], competitors: list[str]) -> dict:
    """Code-only extraction for pasted answers (the $0 path). Positive claims only; no guessing."""
    mentioned, position, seg = business_segment(text, biz["name"])
    claims = []
    if mentioned:
        for f in facts:
            if f["category"] in {"service", "language", "feature"}:
                continue  # absence isn't a claim; presence is too easy to misread without a person
            c = candidates(seg, f, anywhere=f["category"] != "price")
            if c:
                claims.append({"fact_key": f["key"], "value": c[0][0]})
    comps = [c for c in competitors if fold(c) in fold(text)]
    own = " ".join(re.findall(r"[a-z0-9]+", fold(biz["name"]))[:2])
    comps += [n for n in list_names(text) if own and own not in fold(n) and n not in comps]  # real answers name real rivals
    urls = re.findall(r"https?://[^\s)\]>\"']+", text)
    return {"mentioned": mentioned, "position": position, "competitors": comps, "claims": claims,
            "description": "", "descriptors": [], "sentiment": "neutral",
            "sources": [{"url": u.rstrip(".,"), "title": ""} for u in dict.fromkeys(urls)]}
