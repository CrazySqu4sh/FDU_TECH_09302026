"""Five fictional Hispanic-owned demo businesses. The cleaning service is the flagship."""
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
    "plan": "trial",
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
    "plan": "silver",
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

TECH_BUSINESS = {
    "name": "Conecta Tech Refurbished",
    "category": "refurbished laptop and phone store",
    "category_es": "tienda de laptops y celulares reacondicionados",
    "segment": "tech",
    "city": "Houston, TX",
    "website": "https://conectatech.example",
    "competitors": ["ReNew Electronics", "SecondByte", "Gadget Outlet Direct", "LaptopDepot Plus"],
    "owner": "Javier Ruiz (owner)",
    "plan": "gold",
    "facts": [
        ("product.t14.price", "Refurbished ThinkPad T14", "ThinkPad T14 reacondicionado", "Price", "precio",
         "429.00", "price", "system", "Shopify"),
        ("product.t14.stock", "Refurbished ThinkPad T14", "ThinkPad T14 reacondicionado", "Stock", "inventario",
         "in stock", "stock", "system", "Shopify"),
        ("product.t14.ram", "Refurbished ThinkPad T14", "ThinkPad T14 reacondicionado", "RAM", "memoria RAM",
         "16 GB", "spec", "document", "Lenovo spec sheet + intake test"),
        ("product.t14.storage", "Refurbished ThinkPad T14", "ThinkPad T14 reacondicionado", "SSD storage",
         "almacenamiento SSD", "512 GB", "spec", "document", "Lenovo spec sheet + intake test"),
        ("product.t14.touchscreen", "Refurbished ThinkPad T14", "ThinkPad T14 reacondicionado", "Touchscreen",
         "pantalla táctil", "no", "feature", "document", "Lenovo spec sheet"),
        ("product.iphone13.price", "Renewed iPhone 13 128 GB", "iPhone 13 reacondicionado de 128 GB", "Price",
         "precio", "389.00", "price", "system", "Shopify"),
        ("product.iphone13.stock", "Renewed iPhone 13 128 GB", "iPhone 13 reacondicionado de 128 GB", "Stock",
         "inventario", "in stock", "stock", "system", "Shopify"),
        ("product.iphone13.battery", "Renewed iPhone 13 128 GB", "iPhone 13 reacondicionado de 128 GB",
         "Battery health (minimum)", "salud de batería (mínimo)", "90%", "spec", "document", "Grading policy"),
        ("store.warranty", "", "", "Warranty", "garantía", "12", "warranty", "document", "Warranty policy page"),
        ("store.returns", "", "", "Return window", "plazo de devolución", "30", "returns", "document",
         "Return policy page"),
        ("store.shipping", "", "", "Shipping time", "tiempo de envío", "2-4", "shipping", "system",
         "Shopify shipping settings"),
        ("language.spanish", "", "", "Bilingual customer support", "atención al cliente bilingüe", "yes",
         "language", "owner", "Owner confirmed"),
    ],
}


TRADES_BUSINESS = {
    "name": "Hernández Roofing & Remodeling",
    "category": "roofing contractor",
    "category_es": "techero",
    "segment": "trades",
    "city": "Dallas, TX",
    "website": "https://hernandezroofing.example",
    "competitors": ["Lone Star Roofing Pros", "DFW Home Remodelers", "Metroplex Roof & Gutter", "Budget Roof Repair Co."],
    "owner": "Luis Hernández (owner)",
    "plan": "gold",
    "facts": [
        ("credential.license", "", "", "Contractor registration", "registro de contratista", "DAL-CR-48213",
         "license", "document", "City registration record"),
        ("credential.insurance", "", "", "Liability insurance", "seguro de responsabilidad", "yes", "insurance",
         "document", "Certificate of insurance"),
        ("area.service", "", "", "Service area", "zona de servicio", "Dallas, Irving, Garland, Mesquite",
         "service_area", "owner", "Owner confirmed"),
        ("service.free_estimate", "", "", "Free estimates", "estimados gratis", "yes", "service", "owner",
         "Owner confirmed"),
        ("service.emergency", "", "", "Emergency storm repair", "reparación de emergencia por tormenta", "yes",
         "service", "owner", "Owner confirmed"),
        ("price.roof_repair", "", "", "Roof repair (starting at)", "reparación de techo (desde)", "350.00", "price",
         "document", "Price sheet"),
        ("hours.saturday", "", "", "Saturday hours", "horario del sábado", "08:00-14:00", "hours", "document",
         "Google Business Profile"),
        ("contact.phone", "", "", "Phone number", "teléfono", "(214) 555-0176", "contact", "system",
         "Google Business Profile (verified)"),
        ("language.spanish", "", "", "Spanish-speaking crew", "equipo que habla español", "yes", "language", "owner",
         "Owner confirmed"),
    ],
}


CLEANING_BUSINESS = {
    "name": "Brillo Cleaning Co.",
    "category": "house cleaning service",
    "category_es": "servicio de limpieza de casas",
    "segment": "cleaning",
    "city": "Houston, TX",
    "website": "https://brillocleaning.example",
    "competitors": ["Sparkle Maids Houston", "Bayou City Cleaners", "FreshNest Cleaning", "QuickShine Home Services"],
    "owner": "Ana Morales (owner)",
    "plan": "gold",
    "facts": [
        ("price.deep_clean", "", "", "Deep clean, 3 bedrooms (from)", "limpieza profunda, 3 recámaras (desde)",
         "180.00", "price", "document", "Price sheet"),
        ("price.standard_clean", "", "", "Standard clean (from)", "limpieza estándar (desde)", "120.00", "price",
         "document", "Price sheet"),
        ("credential.insurance", "", "", "Bonded and insured", "con fianza y seguro", "yes", "insurance", "document",
         "Certificate of insurance"),
        ("service.background_check", "", "", "Background-checked staff", "personal con revisión de antecedentes",
         "yes", "service", "document", "Background check policy"),
        ("service.move_out", "", "", "Move-out cleaning", "limpieza de mudanza", "yes", "service", "owner",
         "Owner confirmed"),
        ("service.supplies", "", "", "Brings own supplies", "trae sus propios productos", "yes", "service", "owner",
         "Owner confirmed"),
        ("service.eco", "", "", "Eco-friendly products", "productos ecológicos", "yes", "service", "owner",
         "Owner confirmed"),
        ("service.office", "", "", "Office cleaning", "limpieza de oficinas", "yes", "service", "owner",
         "Owner confirmed"),
        ("area.service", "", "", "Service area", "zona de servicio", "Houston, Bellaire, Pasadena, Katy",
         "service_area", "owner", "Owner confirmed"),
        ("hours.saturday", "", "", "Saturday hours", "horario del sábado", "08:00-17:00", "hours", "document",
         "Google Business Profile"),
        ("contact.phone", "", "", "Phone number", "teléfono", "(713) 555-0142", "contact", "system",
         "Google Business Profile (verified)"),
        ("language.spanish", "", "", "Spanish-speaking team", "equipo que habla español", "yes", "language", "owner",
         "Owner confirmed"),
    ],
}


def _insert(db, b: dict) -> int:
    bid = db.execute(
        "INSERT INTO businesses (name, category, category_es, segment, city, website, competitors, plan, "
        "plan_started_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (b["name"], b["category"], b["category_es"], b["segment"], b["city"], b["website"],
         json.dumps(b["competitors"]), b.get("plan", "trial"), now(), now())).lastrowid
    recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="seconds")
    for key, product, product_es, label, label_es, value, cat, ev, src in b["facts"]:
        db.execute(
            "INSERT INTO facts (business_id, key, product, product_es, label, label_es, value, category, evidence, "
            "source, verified_by, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid, key, product, product_es, label, label_es, value, cat, ev, src, b["owner"], recent))
    log(db, bid, "business_created", "seed")
    return bid


def seed(db) -> list[int]:
    """Adds any demo business that isn't there yet, so new demos appear without resetting the database."""
    have = {r[0] for r in db.execute("SELECT name FROM businesses")}
    demo = (CLEANING_BUSINESS, TRADES_BUSINESS, ECOMMERCE_BUSINESS, TECH_BUSINESS, SERVICE_BUSINESS)
    return [_insert(db, b) for b in demo if b["name"] not in have]
