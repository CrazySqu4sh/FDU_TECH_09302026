"""Two fictional Hispanic-owned demo businesses: one service business, one online store."""
import json
from datetime import datetime, timedelta, timezone

from .db import log, now

SERVICE_BUSINESS = {
    "name": "Taller Hernández Auto Repair",
    "category": "auto repair shop",
    "category_es": "taller mecánico",
    "segment": "services",
    "city": "Paterson, NJ",
    "website": "https://tallerhernandez.example",
    "competitors": ["RapidFix Auto", "Garden State Auto Care", "Main Street Motors", "QuickLane Lube"],
    "owner": "Rosa Hernández (owner)",
    # (key, product, product_es, label, label_es, value, category, evidence, source)
    "facts": [
        ("hours.saturday", "", "", "Saturday hours", "horario del sábado", "08:00-16:00", "hours", "document",
         "Website + Google Business Profile"),
        ("hours.sunday", "", "", "Sunday hours", "horario del domingo", "closed", "hours", "owner", "Owner confirmed"),
        ("price.oil_change", "", "", "Oil change", "cambio de aceite", "39.99", "price", "system", "Square POS"),
        ("price.brake_pads", "", "", "Brake pad replacement", "cambio de frenos", "149.00", "price", "system",
         "Square POS"),
        ("service.brake_repair", "", "", "Brake repair", "reparación de frenos", "yes", "service", "owner",
         "Owner confirmed"),
        ("service.toyota", "", "", "Toyota specialist", "especialista en Toyota", "yes", "service", "document",
         "ASE certificate upload"),
        ("service.same_day", "", "", "Same-day repair", "reparación el mismo día", "yes", "service", "owner",
         "Owner confirmed"),
        ("language.spanish", "", "", "Spanish-speaking staff", "personal que habla español", "yes", "language",
         "owner", "Owner confirmed"),
        ("contact.phone", "", "", "Phone number", "teléfono", "(973) 555-0142", "contact", "system",
         "Google Business Profile (verified)"),
    ],
}

ECOMMERCE_BUSINESS = {
    "name": "Piel Fina Leather Co.",
    "category": "handmade leather goods store",
    "category_es": "tienda de artículos de piel",
    "segment": "ecommerce",
    "city": "San Antonio, TX",
    "website": "https://pielfina.example",
    "competitors": ["Rancho Leather Goods", "Casa Huarache", "Artesano Supply", "Frontera Boot Co."],
    "owner": "Marisol Treviño (owner)",
    "facts": [
        ("product.boots.price", "Handmade leather boots", "botas de piel hechas a mano", "Price", "precio",
         "149.00", "price", "system", "Shopify"),
        ("product.boots.stock", "Handmade leather boots", "botas de piel hechas a mano", "Stock", "inventario",
         "in stock", "stock", "system", "Shopify"),
        ("product.huaraches.price", "Leather huaraches", "huaraches de piel", "Price", "precio", "68.00", "price",
         "system", "Shopify"),
        ("product.huaraches.stock", "Leather huaraches", "huaraches de piel", "Stock", "inventario", "in stock",
         "stock", "system", "Shopify"),
        ("product.belt.price", "Tooled leather belt", "cinturón piteado", "Price", "precio", "45.00", "price",
         "system", "eBay listing"),
        ("product.belt.stock", "Tooled leather belt", "cinturón piteado", "Stock", "inventario", "out of stock",
         "stock", "system", "eBay listing"),
        ("store.shipping", "", "", "Shipping time", "tiempo de envío", "3-5", "shipping", "system",
         "Shopify shipping settings"),
        ("store.returns", "", "", "Return window", "plazo de devolución", "30", "returns", "document",
         "Return policy page"),
        ("language.spanish", "", "", "Bilingual customer support", "atención al cliente bilingüe", "yes",
         "language", "owner", "Owner confirmed"),
    ],
}


def _insert(db, b: dict) -> int:
    bid = db.execute(
        "INSERT INTO businesses (name, category, category_es, segment, city, website, competitors, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (b["name"], b["category"], b["category_es"], b["segment"], b["city"], b["website"],
         json.dumps(b["competitors"]), now())).lastrowid
    recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="seconds")
    for key, product, product_es, label, label_es, value, cat, ev, src in b["facts"]:
        db.execute(
            "INSERT INTO facts (business_id, key, product, product_es, label, label_es, value, category, evidence, "
            "source, verified_by, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid, key, product, product_es, label, label_es, value, cat, ev, src, b["owner"], recent))
    log(db, bid, "business_created", "seed")
    return bid


def seed(db) -> list[int]:
    if db.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]:
        return []
    return [_insert(db, ECOMMERCE_BUSINESS), _insert(db, SERVICE_BUSINESS)]
