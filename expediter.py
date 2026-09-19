"""
expediter.py - turn a supplier delay email into a ranked recovery plan.

Three steps, only the first of which is guesswork:

  1. Pull candidate part numbers, quantity and the new ETA out of the email text.
  2. Hand every candidate to Nexar. Parts Nexar recognises are real; the rest are
     dropped. The live API is what separates an MPN from a word like "22WKS".
  3. Rank real sourcing options by how fast each one gets parts to the line,
     using live stock, factory lead time and price breaks.

Stock, pricing, lead time and alternates are live Nexar data. Shipping transit
is the one modelled input - Nexar does not publish carrier transit - and it is
surfaced in the UI as an editable assumption rather than presented as fact.
"""

import re
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------
# Modelled input: inbound transit to the assembly line, in days.
# These are assumptions, NOT Nexar data, and the UI says so.
# --------------------------------------------------------------------------
DISTRIBUTOR_TRANSIT_DAYS = {
    "digi-key": 1,
    "digikey": 1,
    "mouser": 1,
    "arrow": 2,
    "newark": 2,
    "element14": 3,
    "farnell": 3,
    "avnet": 3,
    "tti": 3,
    "future electronics": 3,
    "verical": 3,
    "rs components": 4,
    "onlinecomponents": 4,
    "win source": 6,
    "lcsc": 7,
}
DEFAULT_TRANSIT_DAYS = 3

# Cost of an idle assembly line, per day. Founder-adjustable in the sidebar.
DEFAULT_DOWNTIME_COST_PER_DAY = 2500


# ==========================================================================
# Email parsing
# ==========================================================================
# An MPN is a mixed alphanumeric token. We match liberally and let Nexar be the
# judge - a false candidate simply returns no match and is discarded.
_MPN_CANDIDATE_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9\-_/\.]{3,23}\b")

# Tokens that look like part numbers but never are.
_MPN_STOPWORDS = {
    "WKS", "WEEK", "WEEKS", "DAYS", "MONTH", "MONTHS", "QTY", "PCS", "UNITS",
    "EACH", "USD", "EUR", "MOQ", "ETA", "PO", "POS", "RMA", "ASAP", "FYI",
    "2024", "2025", "2026", "2027", "Q1", "Q2", "Q3", "Q4", "COVID19",
    "AM", "PM", "NO", "RE", "FW", "CC", "BCC", "HTTP", "HTTPS", "WWW", "COM",
}

# Document references - "PO-2291", "RMA_88213", "INV/4471". A bare "PO 4471"
# already falls out, because the two halves fail the stopword and letter tests
# separately; it is only the joined form that survives to look like an MPN.
# Deliberately conservative: the prefix must be followed by digits alone, so
# real catalogue prefixes that happen to collide (TI's REF3025 voltage
# references, SO-8 package codes) are never swallowed. A junk candidate that
# slips through is harmless - it just returns no match - but dropping a real
# MPN loses the part the email was actually about.
_REFERENCE_RE = re.compile(
    r"^(?:PO|SO|WO|ORD|ORDER|RMA|INV|INVOICE|TICKET)[-_/\.]?[0-9]+$",
    re.IGNORECASE,
)

_QTY_PATTERNS = [
    re.compile(r"\bqty[:\s]*([0-9][0-9,]*)", re.IGNORECASE),
    re.compile(r"\bquantity[:\s]*([0-9][0-9,]*)", re.IGNORECASE),
    re.compile(r"\b([0-9][0-9,]*)\s*(?:pcs|pieces|units|ea\b)", re.IGNORECASE),
    re.compile(r"\border(?:ed)?\s+(?:of\s+)?([0-9][0-9,]*)", re.IGNORECASE),
]

_WEEKS_RE = re.compile(r"\b([0-9]{1,3})\s*(?:\+\s*)?(?:week|wk)s?\b", re.IGNORECASE)
_DAYS_RE = re.compile(r"\b([0-9]{1,3})\s*days?\b", re.IGNORECASE)
_MONTHS_RE = re.compile(r"\b([0-9]{1,2})\s*months?\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(20[0-9]{2})-([01]?[0-9])-([0-3]?[0-9])\b")
_US_DATE_RE = re.compile(r"\b([01]?[0-9])/([0-3]?[0-9])/(20[0-9]{2})\b")


def extract_mpn_candidates(text, limit=12):
    """Candidate part numbers, in the order they appear. Nexar does the filtering."""
    seen, candidates = set(), []
    for match in _MPN_CANDIDATE_RE.finditer(text or ""):
        token = match.group(0).strip(".-_/")
        if len(token) < 5:
            continue
        upper = token.upper()
        if upper in _MPN_STOPWORDS or upper in seen:
            continue
        if _REFERENCE_RE.match(token):
            continue
        digits = sum(c.isdigit() for c in token)
        letters = sum(c.isalpha() for c in token)
        # Real MPNs mix letters and digits; dates, counts and words do not.
        if digits < 2 or letters < 1:
            continue
        if token.replace(".", "").replace(",", "").isdigit():
            continue
        seen.add(upper)
        candidates.append(token)
        if len(candidates) >= limit:
            break
    return candidates


def extract_quantity(text, default=100):
    for pattern in _QTY_PATTERNS:
        match = pattern.search(text or "")
        if match:
            try:
                value = int(match.group(1).replace(",", ""))
            except ValueError:
                continue
            if 0 < value <= 10_000_000:
                return value
    return default


def extract_delay_days(text, today=None):
    """
    How many days out the supplier has pushed the shipment.

    Understands "22 weeks", "90 days", "4 months" and explicit dates.
    Returns (days, description) or (None, None).
    """
    today = today or date.today()
    text = text or ""

    # A delay email usually quotes both the old and the new schedule ("was 6
    # weeks, now 22"; "original 2026-10-02 / revised 2027-01-15"). The slip is
    # the worst number on the page, so take the furthest-out value, not the first.
    weeks = [int(m.group(1)) for m in _WEEKS_RE.finditer(text)]
    weeks = [w for w in weeks if 0 < w <= 200]
    if weeks:
        worst = max(weeks)
        return worst * 7, "{} weeks".format(worst)

    months = [int(m.group(1)) for m in _MONTHS_RE.finditer(text)]
    months = [m for m in months if 0 < m <= 48]
    if months:
        worst = max(months)
        return worst * 30, "{} months".format(worst)

    days = [int(m.group(1)) for m in _DAYS_RE.finditer(text)]
    days = [d for d in days if 0 < d <= 2000]
    if days:
        worst = max(days)
        return worst, "{} days".format(worst)

    deltas = []
    for pattern, order in ((_ISO_DATE_RE, "ymd"), (_US_DATE_RE, "mdy")):
        for match in pattern.finditer(text):
            try:
                if order == "ymd":
                    target = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                else:
                    target = date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
            except ValueError:
                continue
            delta = (target - today).days
            if 0 < delta <= 2000:
                deltas.append((delta, target))
    if deltas:
        delta, target = max(deltas, key=lambda d: d[0])
        return delta, target.isoformat()

    return None, None


# ==========================================================================
# Sourcing options from live Nexar data
# ==========================================================================
def transit_days_for(company_name, overrides=None):
    """Modelled inbound transit for a distributor. Not Nexar data."""
    table = dict(DISTRIBUTOR_TRANSIT_DAYS)
    if overrides:
        table.update({k.lower(): v for k, v in overrides.items()})
    low = (company_name or "").lower()
    for key, days in table.items():
        if key in low:
            return days
    return DEFAULT_TRANSIT_DAYS


def _price_at_quantity(prices, quantity):
    """Unit price at the break that applies to this order size."""
    usable = []
    for row in prices or []:
        try:
            break_qty = int(row.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        unit = row.get("convertedPrice")
        if unit is None:
            unit = row.get("price")
        if unit is None:
            continue
        try:
            unit = float(unit)
        except (TypeError, ValueError):
            continue
        currency = row.get("convertedCurrency") or row.get("currency") or "USD"
        usable.append((break_qty, unit, currency))

    if not usable:
        return None, None
    usable.sort(key=lambda r: r[0])
    applicable = [r for r in usable if r[0] <= quantity]
    chosen = applicable[-1] if applicable else usable[0]
    return chosen[1], chosen[2]


def sourcing_options(part, quantity, transit_overrides=None):
    """
    Flatten a Nexar part into ranked, orderable options.

    Each option records how soon that distributor can put the full quantity on
    the assembly line, and what it costs to do so.
    """
    options = []
    for seller in part.get("sellers") or []:
        company = ((seller.get("company") or {}).get("name")) or "Unknown distributor"
        transit = transit_days_for(company, transit_overrides)

        for offer in seller.get("offers") or []:
            try:
                stock = int(offer.get("inventoryLevel") or 0)
            except (TypeError, ValueError):
                stock = 0
            lead_days = offer.get("factoryLeadDays")
            try:
                lead_days = int(lead_days) if lead_days is not None else None
            except (TypeError, ValueError):
                lead_days = None

            unit_price, currency = _price_at_quantity(offer.get("prices"), quantity)

            if stock >= quantity:
                days_to_line = transit
                coverage = "full"
            elif stock > 0:
                # Partial stock still helps - it can keep the line running while
                # the balance ships on the factory lead time.
                days_to_line = lead_days + transit if lead_days is not None else None
                coverage = "partial"
            else:
                days_to_line = lead_days + transit if lead_days is not None else None
                coverage = "backorder"

            try:
                moq = int(offer.get("moq") or 0)
            except (TypeError, ValueError):
                moq = 0

            options.append({
                "distributor": company,
                "stock": stock,
                "covers_order": stock >= quantity,
                "coverage": coverage,
                "factory_lead_days": lead_days,
                "transit_days": transit,
                "days_to_line": days_to_line,
                "unit_price": unit_price,
                "currency": currency or "USD",
                "total_cost": round(unit_price * quantity, 2) if unit_price else None,
                "moq": moq,
                "packaging": offer.get("packaging") or "",
                "url": offer.get("clickUrl") or "",
            })

    # Fastest first; among equals, cheapest. Unknown timing sinks to the bottom.
    options.sort(key=lambda o: (
        o["days_to_line"] is None,
        o["days_to_line"] if o["days_to_line"] is not None else 9999,
        o["total_cost"] is None,
        o["total_cost"] if o["total_cost"] is not None else float("inf"),
    ))
    return options


def best_option(options, require_full=True):
    """Fastest option that can actually cover the order, if one exists."""
    if require_full:
        full = [o for o in options if o["covers_order"] and o["days_to_line"] is not None]
        if full:
            return full[0]
    timed = [o for o in options if o["days_to_line"] is not None]
    return timed[0] if timed else (options[0] if options else None)


def part_summary(part, quantity, transit_overrides=None):
    """Everything the UI needs about one resolved part."""
    options = sourcing_options(part, quantity, transit_overrides)
    chosen = best_option(options)
    manufacturer = (part.get("manufacturer") or {}).get("name") or "Unknown"
    median = part.get("medianPrice1000") or {}
    median_price = median.get("convertedPrice") or median.get("price")

    return {
        "mpn": part.get("mpn"),
        "name": part.get("name") or part.get("shortDescription") or "",
        "description": part.get("shortDescription") or "",
        "manufacturer": manufacturer,
        "category": (part.get("category") or {}).get("name") or "",
        "total_avail": part.get("totalAvail") or 0,
        "median_price_1000": median_price,
        "octopart_url": part.get("octopartUrl") or "",
        "datasheet": (part.get("bestDatasheet") or {}).get("url") or "",
        "options": options,
        "best": chosen,
        "similar": [
            {
                "mpn": s.get("mpn"),
                "name": s.get("name") or "",
                "manufacturer": (s.get("manufacturer") or {}).get("name") or "",
                "total_avail": s.get("totalAvail") or 0,
            }
            for s in (part.get("similarParts") or [])
            if s.get("mpn")
        ],
    }


# ==========================================================================
# ROI
# ==========================================================================
def recovery_roi(delay_days, best_days_to_line, downtime_cost_per_day):
    """Days of line-downtime avoided by expediting instead of waiting."""
    if delay_days is None or best_days_to_line is None:
        return None
    days_saved = max(delay_days - best_days_to_line, 0)
    return {
        "delay_days": delay_days,
        "recovery_days": best_days_to_line,
        "days_saved": days_saved,
        "dollars_saved": days_saved * downtime_cost_per_day,
        "weeks_saved": round(days_saved / 7.0, 1),
    }


def eta_date(days_from_now, today=None):
    today = today or date.today()
    if days_from_now is None:
        return None
    return today + timedelta(days=int(days_from_now))


def format_date(value):
    if value is None:
        return "unknown"
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %d, %Y")
    return str(value)
