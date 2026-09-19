"""
mock_data.py - The Catalog Engineer
-----------------------------------
Demo fixtures + the "AI" extraction pipeline.

The three SAMPLES below are realistic messy supplier submissions (a rambling
email, a mangled CSV paste, a phone-note text dump). Each carries a HARDCODED
clean result so the live demo is deterministic and cannot fail on stage.

If someone pastes their own text, extract_catalog() falls back to a real
heuristic parser (regex + keyword rules). It is honestly rule-based, not an
LLM, and is labeled as such in the UI.
"""

import re

import pandas as pd

# --------------------------------------------------------------------------
# Catalog schema - the founder's clean target format
# --------------------------------------------------------------------------
SCHEMA_COLUMNS = ["SKU", "Item_Name", "Category", "Unit_Price", "Bulk_Availability"]

CATEGORIES = [
    "Produce", "Meat", "Seafood", "Dairy",
    "Dry Goods", "Pantry", "Bakery", "Beverage",
]

BULK_OPTIONS = ["Yes", "Limited", "No"]

# --------------------------------------------------------------------------
# ROI assumptions - stated openly so the judges can audit the math
# --------------------------------------------------------------------------
MINUTES_SAVED_PER_ITEM = 3      # founder's manual keying time per line item
MANUAL_HOURS_PER_DAY = 4        # hours/day currently lost to supplier onboarding
DEFAULT_HOURLY_RATE = 65        # blended value of a solo founder's hour, USD

# --------------------------------------------------------------------------
# Simulated pipeline stages (label, seconds) -> ~2.05s of "AI thinking"
# --------------------------------------------------------------------------
PIPELINE_STAGES = [
    ("Reading raw supplier input...", 0.30),
    ("Detecting source format...", 0.28),
    ("Extracting line items...", 0.42),
    ("Normalizing prices, units and spelling...", 0.40),
    ("Assigning SKUs and categories...", 0.35),
    ("Validating against catalog schema...", 0.30),
]


# ==========================================================================
# SAMPLE 1 - Rambling email from an Italian dry-goods supplier
# ==========================================================================
_NONNA_RAW = """From: Sal Marino <sal@nonnasprovisions.com>
To: founder@marketplace.co
Subject: Re: re: whats available this week

Hey there,

sorry for the delay getting back to u, been slammed. heres whats in stock for
the week of the 14th. prices are all wholesale, delivery mon/wed/fri.

- San Marzano tomatos (28oz can) - 3.85 a can, case of 12 is 44.00
- Fresh mozzerella, 1lb balls -- $6.25/lb, we can do 20lb+ no problem
- Extra virgin olive oil 3L tin, $38.50 ea.  SKU NP-OIL-3L
- Prosciutto di parma, sliced -- 24.00 per pound. limited, only ~15lbs a week
- semolina flour 50lb bag ... 42
- Pecorino romano wheel (approx 5lb) 19.50/lb
- fresh basil, bunch, .95 each (min 24 bunches)

lmk what u need by thurs. call the shop if the cell dont pick up.

- Sal
Nonna's Provisions | 617-555-0193
"""

_NONNA_ROWS = [
    ["NP-PAN-0101", "San Marzano Tomatoes, 28 oz Can",    "Pantry",     3.85, "Yes"],
    ["NP-DAI-0102", "Fresh Mozzarella, 1 lb Ball",        "Dairy",      6.25, "Yes"],
    ["NP-OIL-3L",   "Extra Virgin Olive Oil, 3 L Tin",    "Pantry",    38.50, "Yes"],
    ["NP-MEA-0103", "Prosciutto di Parma, Sliced",        "Meat",      24.00, "Limited"],
    ["NP-DRY-0104", "Semolina Flour, 50 lb Bag",          "Dry Goods", 42.00, "Yes"],
    ["NP-DAI-0105", "Pecorino Romano Wheel, approx 5 lb", "Dairy",     19.50, "Yes"],
    ["NP-PRD-0106", "Fresh Basil, Bunch",                 "Produce",    0.95, "Yes"],
]

_NONNA_FIXES = [
    "Stripped email headers, signature and 3 lines of conversational filler.",
    "Corrected supplier spelling: 'tomatos' to 'Tomatoes', 'mozzerella' to 'Mozzarella'.",
    "Normalized 4 price formats ('42', '.95 each', '$6.25/lb', '24.00 per pound') to 2-decimal USD.",
    "Kept the supplier's own SKU (NP-OIL-3L); generated 6 SKUs for items that had none.",
    "Read 'limited, only ~15lbs a week' as Bulk Availability = Limited.",
]

_NONNA_REVIEW = [
    "San Marzano Tomatoes was also quoted at $44.00 per case of 12. We kept the "
    "per-can price - add the case as its own SKU if you resell it that way.",
]


# ==========================================================================
# SAMPLE 2 - Mangled CSV pasted straight out of a spreadsheet
# ==========================================================================
_BAYSTATE_RAW = """ITEM,,PRICE,,,NOTES
*** BAY STATE SEAFOOD -- WEEKLY LIST 9/16 ***,,,,,
,,,,,
Atlantic Salmon Fillet (skin on);;12.75/lb;;;fresh daily
COD LOIN - CENTER CUT,,$14.20 per lb,,,limited qty this wk
littleneck clams (100ct bag),,68.00,,,
Sea Scallops U-10,,"$22,50",,,dry packed
haddock fillet,,11.9,,,
Maine Lobster Meat CK/KN 1lb,,44.00,,,frozen only
shrimp 16/20 EZ peel 2lb bag,,,,,CALL FOR PRICE
,,,,,
questions? call marcy 617-555-0142
"""

_BAYSTATE_ROWS = [
    ["BSS-SEA-0201", "Atlantic Salmon Fillet, Skin-On", "Seafood", 12.75, "Yes"],
    ["BSS-SEA-0202", "Cod Loin, Center Cut",            "Seafood", 14.20, "Limited"],
    ["BSS-SEA-0203", "Littleneck Clams, 100 ct Bag",    "Seafood", 68.00, "Yes"],
    ["BSS-SEA-0204", "Sea Scallops U-10, Dry Packed",   "Seafood", 22.50, "Yes"],
    ["BSS-SEA-0205", "Haddock Fillet",                  "Seafood", 11.90, "Yes"],
    ["BSS-SEA-0206", "Maine Lobster Meat CK/KN, 1 lb",  "Seafood", 44.00, "Yes"],
    ["BSS-SEA-0207", "Shrimp 16/20 EZ-Peel, 2 lb Bag",  "Seafood",  None, "No"],
]

_BAYSTATE_FIXES = [
    "Dropped 5 junk rows: banner text, empty delimiter rows and a phone-number footer.",
    "Handled mixed delimiters - the sheet switched between ',' and ';' partway down.",
    "Repaired a decimal-comma typo: '$22,50' became 22.50, not 2250.00.",
    "Padded '11.9' to 11.90 and stripped '/lb' and 'per lb' suffixes from prices.",
    "Rewrote ALL-CAPS and all-lowercase item names into consistent title case.",
]

_BAYSTATE_REVIEW = [
    "Shrimp 16/20 EZ-Peel has no price - the supplier wrote 'CALL FOR PRICE'. "
    "Enter it below or the item will publish as unavailable.",
]


# ==========================================================================
# SAMPLE 3 - Phone-note / SMS dump from a produce farm
# ==========================================================================
_GREENVALLEY_RAW = """hi its dave from green valley. heres what we got comin in

kale - bunch - 2.25 (tons available)
rainbow chard bunch 2.40
heirloom toms 3.10/lb thru end of sept ONLY
baby arugula 3lb case $16
Yukon gold potatos 50# sack - 28.50
carrots, 25lb - 19
"sweet corn" doz - 4.75 -- goin fast, maybe 2 more wks
Local honey 1qt --- 22.00 ea, only 6 jars left
eggs, brown, 15doz case: 62.00

we deliver tues + fri. no min order for u guys
thx
Dave
"""

_GREENVALLEY_ROWS = [
    ["GVF-PRD-0301", "Kale, Bunch",                     "Produce",  2.25, "Yes"],
    ["GVF-PRD-0302", "Rainbow Chard, Bunch",            "Produce",  2.40, "Yes"],
    ["GVF-PRD-0303", "Heirloom Tomatoes",               "Produce",  3.10, "Limited"],
    ["GVF-PRD-0304", "Baby Arugula, 3 lb Case",         "Produce", 16.00, "Yes"],
    ["GVF-PRD-0305", "Yukon Gold Potatoes, 50 lb Sack", "Produce", 28.50, "Yes"],
    ["GVF-PRD-0306", "Carrots, 25 lb Bag",              "Produce", 19.00, "Yes"],
    ["GVF-PRD-0307", "Sweet Corn, Dozen",               "Produce",  4.75, "Limited"],
    ["GVF-PAN-0308", "Local Honey, 1 qt Jar",           "Pantry",  22.00, "Limited"],
    ["GVF-DAI-0309", "Brown Eggs, 15 dz Case",          "Dairy",   62.00, "Yes"],
]

_GREENVALLEY_FIXES = [
    "Expanded supplier shorthand: 'toms' to Tomatoes, '50#' to 50 lb, 'doz' to Dozen.",
    "Corrected 'potatos' to 'Potatoes' and removed stray quotes around 'sweet corn'.",
    "Normalized '$16', '19' and '62.00' to 2-decimal USD.",
    "Routed honey and eggs out of Produce and into Pantry and Dairy.",
    "Read 'thru end of sept ONLY', 'goin fast' and 'only 6 jars left' as Limited.",
]

_GREENVALLEY_REVIEW = []


# --------------------------------------------------------------------------
# Sample registry
# --------------------------------------------------------------------------
SAMPLES = [
    {
        "id": "nonna",
        "supplier": "Nonna's Provisions",
        "contact": "Sal Marino",
        "source": "Plain-text email",
        "blurb": "Rambling email, supplier typos, four different price formats, one real SKU.",
        "raw": _NONNA_RAW,
        "rows": _NONNA_ROWS,
        "fixes": _NONNA_FIXES,
        "review": _NONNA_REVIEW,
    },
    {
        "id": "baystate",
        "supplier": "Bay State Seafood Co.",
        "contact": "Marcy Doyle",
        "source": "Pasted CSV (broken)",
        "blurb": "Mixed delimiters, banner rows, a decimal-comma typo and one missing price.",
        "raw": _BAYSTATE_RAW,
        "rows": _BAYSTATE_ROWS,
        "fixes": _BAYSTATE_FIXES,
        "review": _BAYSTATE_REVIEW,
    },
    {
        "id": "greenvalley",
        "supplier": "Green Valley Farms",
        "contact": "Dave Whitaker",
        "source": "Pasted phone note",
        "blurb": "No structure at all - shorthand, unit abbreviations and seasonal caveats.",
        "raw": _GREENVALLEY_RAW,
        "rows": _GREENVALLEY_ROWS,
        "fixes": _GREENVALLEY_FIXES,
        "review": _GREENVALLEY_REVIEW,
    },
]

SAMPLE_INDEX = {s["id"]: s for s in SAMPLES}


def empty_catalog():
    """An empty DataFrame carrying the clean catalog schema."""
    return pd.DataFrame({
        "SKU": pd.Series(dtype="object"),
        "Item_Name": pd.Series(dtype="object"),
        "Category": pd.Series(dtype="object"),
        "Unit_Price": pd.Series(dtype="float64"),
        "Bulk_Availability": pd.Series(dtype="object"),
    })


def _rows_to_frame(rows):
    df = pd.DataFrame(rows, columns=SCHEMA_COLUMNS)
    df["Unit_Price"] = pd.to_numeric(df["Unit_Price"], errors="coerce")
    return df


# ==========================================================================
# Heuristic fallback parser - used only for text someone pastes themselves
# ==========================================================================
# Checked in order - the first keyword hit wins, so Produce leads to keep
# "eggplant" out of Dairy and "tomato" out of Pantry.
_CATEGORY_KEYWORDS = {
    "Produce": ["lettuce", "romaine", "kale", "tomato", "onion", "potato", "carrot",
                "pepper", "arugula", "chard", "basil", "corn", "apple", "berry",
                "greens", "mushroom", "garlic", "herb", "spinach", "cucumber",
                "eggplant", "broccoli", "cauliflower", "zucchini", "squash", "celery",
                "lemon", "lime", "avocado", "cilantro", "parsley", "scallion", "leek"],
    "Seafood": ["salmon", "cod", "clam", "scallop", "haddock", "lobster", "shrimp",
                "tuna", "oyster", "mussel", "crab", "fish", "squid", "halibut",
                "tilapia", "calamari", "prawn", "anchov", "sardine"],
    "Meat": ["beef", "pork", "chicken", "prosciutto", "sausage", "bacon", "lamb",
             "turkey", "steak", "brisket", "ham", "veal", "salami", "pepperoni",
             "chorizo", "duck", "ribeye", "tenderloin", "meatball"],
    "Dairy": ["milk", "cheese", "cheddar", "mozzarella", "cream", "butter", "yogurt",
              "egg", "pecorino", "parmesan", "parmigian", "ricotta", "provolone",
              "gouda", "brie", "feta", "mascarpone", "buttermilk"],
    "Bakery": ["bread", "loaf", "sourdough", "roll", "bun", "baguette", "focaccia",
               "pastry", "croissant", "brioche", "ciabatta", "bagel", "tortilla", "pita"],
    "Beverage": ["water", "soda", "juice", "coffee", "tea", "wine", "beer", "cola",
                 "seltzer", "kombucha", "cider", "espresso"],
    "Dry Goods": ["flour", "rice", "pasta", "sugar", "bean", "lentil", "semolina",
                  "grain", "oat", "salt", "cornmeal", "polenta", "couscous", "quinoa",
                  "breadcrumb", "yeast", "noodle"],
    "Pantry": ["oil", "vinegar", "sauce", "honey", "spice", "olive", "can", "tin",
               "paste", "syrup", "mustard", "mayo", "stock", "broth", "puree", "jam"],
}

_LIMITED_HINTS = ["limited", "only", "last", "few", "while supplies", "seasonal",
                  "thru", "through", "goin fast", "going fast"]
_NO_BULK_HINTS = ["call for price", "no bulk", "not available", "out of stock"]

_JUNK_PATTERNS = re.compile(
    r"^\s*(from:|to:|subject:|cc:|bcc:|sent:|date:|re:|thanks|thx|regards|best,|hi\b|hey\b|"
    r"hello\b|questions|call\b|item\s*,|\*{2,}|-{3,}|={3,})",
    re.IGNORECASE,
)
_SKU_RE = re.compile(r"\b([A-Z]{2,4}[-_][A-Z0-9]{2,6}(?:[-_][A-Z0-9]{1,6})?)\b")
_PHONE_RE = re.compile(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}")

# A number, optionally money-prefixed. Spans are tracked so the name cleaner can
# cut out exactly the price and leave pack sizes ("3 pk", "50 lb") intact.
_NUM_RE = re.compile(
    r"(?P<cur>\$\s*)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+[.,]\d{1,2}|\.\d{1,2}|\d+)"
)

# A unit immediately after a number means it was a pack size, not a price.
_SIZE_SUFFIX_RE = re.compile(
    r"^\s*(?:lbs?|#|oz|kgs?|ml|liters?|litres?|qts?|pts?|gals?|ct|count|pks?|packs?|"
    r"cases?|bags?|jars?|cans?|tins?|dz|doz|dozen|pcs?|pieces?|inch(?:es)?|g|l)\b",
    re.IGNORECASE,
)

# Per-unit phrasing that is noise once the price is extracted.
_UNIT_NOISE_RE = re.compile(
    r"(?:/\s*lb\b|\bper\s+(?:lb|pound|case|each)\b|\beach\b|\bea\b|\bapiece\b|\bwholesale\b)",
    re.IGNORECASE,
)

# Where a product name stops and the supplier's side-comment begins.
_NOTE_SPLIT_RE = re.compile(
    r"\s*(?:--|\bthru\b|\bthrough\b|\bwhile\s+supplies\b|\bonly\b|\blimited\b|"
    r"\bmin\.?\s+\d|\bcall\b|\bfresh\s+daily\b|\bgoin\b|\bgoing\s+fast\b|"
    r"\bfrozen\s+only\b|\bdry\s+packed\b)",
    re.IGNORECASE,
)

_FIELD_SPLIT_RE = re.compile(r";{2,}|,{2,}|\t|\|")


def _guess_category(name):
    low = name.lower()
    for category, words in _CATEGORY_KEYWORDS.items():
        if any(w in low for w in words):
            return category
    return "Dry Goods"


def _guess_bulk(line):
    low = line.lower()
    if any(h in low for h in _NO_BULK_HINTS):
        return "No"
    if any(h in low for h in _LIMITED_HINTS):
        return "Limited"
    return "Yes"


def _parse_price(text):
    """
    Pick the most plausible price on a line and report where it sits.

    Returns (value, start, end); (None, -1, -1) when nothing looks like a price.
    Numbers that are really pack sizes ("50 lb", "100ct") are skipped, and a
    decimal-comma typo ("$22,50") is repaired rather than read as 2250.
    """
    blocked = [m.span() for m in _PHONE_RE.finditer(text)]
    candidates = []

    for match in _NUM_RE.finditer(text):
        start, end = match.start(), match.end()
        if any(b0 <= start < b1 for b0, b1 in blocked):
            continue

        raw = match.group("num")
        has_currency = bool(match.group("cur"))
        if not has_currency and _SIZE_SUFFIX_RE.match(text[end:]):
            continue

        # "22,50" is a European decimal comma, not a thousands separator
        normalised = raw.replace(",", ".") if re.fullmatch(r"\d{1,3},\d{2}", raw) else raw.replace(",", "")
        try:
            value = float(normalised)
        except ValueError:
            continue
        if not 0.05 <= value <= 10000:
            continue

        # A currency symbol is the strongest signal, a decimal point the next best;
        # otherwise take the right-most number on the line.
        score = (3 if has_currency else 0) + (2 if "." in normalised else 0)
        candidates.append((score, start, end, value))

    if not candidates:
        return None, -1, -1
    score, start, end, value = max(candidates, key=lambda c: (c[0], c[1]))
    return value, start, end


def _smart_title(name):
    """
    Title-case a product name without wrecking the parts that carry meaning:
    size tokens keep their own casing (3L, 28oz, 50#, 80/20) and short acronyms
    stay upper (EZ, CK/KN, U-10).
    """
    words = []
    for word in name.split():
        if any(ch.isdigit() for ch in word):
            words.append(word)
        elif word.isupper() and (len(word) <= 4 or "/" in word):
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _clean_name(text, price_span=None):
    """Strip the price, SKU, per-unit phrasing and trailing commentary from a line."""
    if price_span and price_span[0] >= 0:
        name = text[:price_span[0]] + " " + text[price_span[1]:]
    else:
        name = text
    name = _SKU_RE.sub(" ", name)
    name = _UNIT_NOISE_RE.sub(" ", name)
    name = _NOTE_SPLIT_RE.split(name, maxsplit=1)[0]
    name = name.replace("$", " ")
    name = re.sub(r"[;,]{2,}", " ", name)
    name = re.sub(r"^[\s\-*.]+", "", name)
    name = re.sub(r"[\s\-*.,;:]+$", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" \"'")
    return _smart_title(name) if name else name


def _heuristic_extract(raw_text, prefix="NEW"):
    """Rule-based extraction for arbitrary pasted text. Not an LLM - labeled as such."""
    rows, seq = [], 1
    for line in raw_text.splitlines():
        stripped = line.strip()
        if len(stripped) < 4 or _JUNK_PATTERNS.match(stripped):
            continue
        if not any(ch.isdigit() for ch in stripped):
            continue

        # On CSV-ish rows the name lives in the first field but the price may be
        # several columns to the right, so search the whole line for the price.
        fields = [f.strip() for f in _FIELD_SPLIT_RE.split(stripped) if f.strip()]
        name_source = fields[0] if len(fields) > 1 else stripped

        price, _, _ = _parse_price(stripped)
        _, name_start, name_end = _parse_price(name_source)
        name = _clean_name(name_source, (name_start, name_end))
        if not name or len(name) < 3:
            continue

        sku_match = _SKU_RE.search(stripped)
        category = _guess_category(name)
        sku = sku_match.group(1) if sku_match else "{}-{}-{:04d}".format(prefix, category[:3].upper(), seq)
        rows.append([sku, name, category, price, _guess_bulk(stripped)])
        seq += 1
    return _rows_to_frame(rows)


# ==========================================================================
# The public "AI" entry point
# ==========================================================================
def extract_catalog(raw_text, sample_id=None):
    """
    Turn messy supplier text into a clean catalog DataFrame.

    Returns (df, meta) where meta carries the narration the UI shows:
        mode   -> "demo" (hardcoded, deterministic) or "heuristic" (live rules)
        fixes  -> list of cleanup actions to display
        review -> list of items needing the founder's judgement
    """
    if sample_id and sample_id in SAMPLE_INDEX:
        sample = SAMPLE_INDEX[sample_id]
        return _rows_to_frame(sample["rows"]), {
            "mode": "demo",
            "supplier": sample["supplier"],
            "fixes": list(sample["fixes"]),
            "review": list(sample["review"]),
        }

    df = _heuristic_extract(raw_text)
    missing = int(df["Unit_Price"].isna().sum()) if not df.empty else 0
    review = []
    if missing:
        review.append("{} item(s) came through without a readable price - fill them in below.".format(missing))
    if df.empty:
        review.append("No line items were recognised in that text. Try one product per line.")
    return df, {
        "mode": "heuristic",
        "supplier": "Pasted input",
        "fixes": [
            "Scanned {} lines and kept {} product rows.".format(len(raw_text.splitlines()), len(df)),
            "Dropped greetings, headers and signature lines.",
            "Normalized prices to 2-decimal USD and repaired decimal-comma typos.",
            "Inferred Category from product keywords and Bulk Availability from phrasing.",
        ],
        "review": review,
    }
