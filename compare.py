"""
compare.py - scoring a candidate part against a reference part.

The score answers one question: "if I can't get the part I wanted, how good a
move is this one instead?" It is a weighted blend of four sub-scores, each on
0-100 and each reported separately so the number is auditable rather than
magic. A founder should be able to disagree with the weighting and re-run it,
which is why the weights are sliders in the UI rather than constants here.

Deliberate limitation: the Fit sub-score is a HEURISTIC based on manufacturer
and category metadata. It is not an electrical or pin compatibility check, and
nothing here reads a datasheet. It narrows the field for a human to review; it
does not approve a substitution.
"""

DEFAULT_WEIGHTS = {
    "price": 0.30,
    "availability": 0.25,
    "speed": 0.25,
    "fit": 0.20,
}

# Days-to-line at which the speed sub-score bottoms out.
SPEED_HORIZON_DAYS = 90


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def price_score(reference_price, candidate_price):
    """
    100 = free, 50 = same price as the reference, 0 = double or worse.

    An unpriced candidate scores 0 rather than being treated as cheap.
    """
    if candidate_price is None or reference_price is None or reference_price <= 0:
        return 0.0
    if candidate_price <= 0:
        return 0.0
    delta = (reference_price - candidate_price) / reference_price
    if delta >= 0:                       # cheaper
        return _clamp(50 + 50 * min(delta, 1.0))
    return _clamp(50 * max(0.0, 1.0 + delta))   # dearer; 0 at 2x reference


def availability_score(stock, quantity):
    """100 when the candidate alone covers the order, pro-rata below that."""
    if not quantity or quantity <= 0:
        return 0.0
    if stock is None:
        return 0.0
    return _clamp(100.0 * min(stock / float(quantity), 1.0))


def speed_score(days_to_line):
    """100 for same-day, decaying linearly to 0 at the horizon."""
    if days_to_line is None:
        return 0.0
    return _clamp(100.0 * max(0.0, 1.0 - days_to_line / float(SPEED_HORIZON_DAYS)))


def fit_score(reference, candidate):
    """
    Drop-in likelihood from metadata alone - a filter, not an approval.

    Same manufacturer and same category is the strongest signal available
    without reading a datasheet.
    """
    score = 30.0
    ref_mfr = (reference.get("manufacturer") or "").strip().lower()
    cand_mfr = (candidate.get("manufacturer") or "").strip().lower()
    ref_cat = (reference.get("category") or "").strip().lower()
    cand_cat = (candidate.get("category") or "").strip().lower()

    if ref_mfr and ref_mfr == cand_mfr:
        score += 35.0
    if ref_cat and ref_cat == cand_cat:
        score += 35.0
    return _clamp(score)


def _unit_price(summary):
    best = summary.get("best")
    if best and best.get("unit_price") is not None:
        return best["unit_price"]
    return summary.get("median_price_1000")


def score_candidate(reference, candidate, quantity, weights=None):
    """
    Score one candidate against the reference part.

    Returns the blended total plus every input that produced it, so the UI can
    show its working.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    ref_price = _unit_price(reference)
    cand_price = _unit_price(candidate)
    best = candidate.get("best") or {}

    parts = {
        "price": price_score(ref_price, cand_price),
        "availability": availability_score(candidate.get("total_avail"), quantity),
        "speed": speed_score(best.get("days_to_line")),
        "fit": fit_score(reference, candidate),
    }
    total = sum(parts[key] * weights.get(key, 0.0) for key in parts)

    savings_pct = None
    savings_total = None
    if ref_price and cand_price is not None and ref_price > 0:
        savings_pct = (ref_price - cand_price) / ref_price * 100.0
        savings_total = (ref_price - cand_price) * quantity

    return {
        "mpn": candidate.get("mpn"),
        "manufacturer": candidate.get("manufacturer"),
        "category": candidate.get("category"),
        "description": candidate.get("name") or candidate.get("description") or "",
        "unit_price": cand_price,
        "reference_price": ref_price,
        "savings_pct": savings_pct,
        "savings_total": savings_total,
        "total_avail": candidate.get("total_avail"),
        "days_to_line": best.get("days_to_line"),
        "distributor": best.get("distributor"),
        "order_total": best.get("total_cost"),
        "covers_order": best.get("covers_order", False),
        "score_price": parts["price"],
        "score_availability": parts["availability"],
        "score_speed": parts["speed"],
        "score_fit": parts["fit"],
        "score": round(total, 1),
        "is_cheaper": bool(cand_price is not None and ref_price and cand_price < ref_price),
    }


def compare_parts(reference, candidates, quantity, weights=None, cheaper_only=False):
    """Score every candidate against the reference, best first."""
    rows = []
    for candidate in candidates:
        if candidate.get("mpn") == reference.get("mpn"):
            continue
        row = score_candidate(reference, candidate, quantity, weights)
        if cheaper_only and not row["is_cheaper"]:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def verdict(row):
    """A short, human reading of the score."""
    score = row["score"]
    if score >= 75:
        return "Strong swap"
    if score >= 60:
        return "Worth a look"
    if score >= 45:
        return "Marginal"
    return "Weak"
