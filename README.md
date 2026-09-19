# The Catalog Engineer

**AINU Misneach 2026 — Track 01:** build the hire an early founder can't afford yet.

---

## Founder Persona

A **non-technical solo founder** running a B2B wholesale marketplace that connects
local restaurants to local suppliers. She has no engineer, no ops hire, and no budget
for either.

## The Bottleneck

**Supplier onboarding.** Every supplier sends inventory in a different mess — a
rambling email, a CSV mangled by three different spreadsheet apps, a note typed on a
phone. There is no template anyone will actually follow.

The founder personally reads each submission and retypes it into her marketplace's
schema: SKU, item name, category, unit price, bulk availability. It costs her about
**4 hours a day**, and it is the single thing blocking her from adding suppliers faster.

## The Hire

The Catalog Engineer is the catalog operations associate she would hire if she had the
money. Messy text in, clean database rows out, with her keeping final approval on
every row.

---

## What it does

1. **Ingest** — paste or forward whatever the supplier sent. No template, no cleanup.
2. **Extract** — pull out line items and normalize them into the catalog schema:
   `SKU · Item_Name · Category · Unit_Price · Bulk_Availability`
3. **Explain** — show exactly what it corrected (typos, price formats, generated SKUs)
   so the founder can trust it rather than re-check it.
4. **Flag** — surface the rows needing a human decision (a missing price, an ambiguous
   case quote) instead of silently guessing.
5. **Approve** — the founder edits anything in an inline table and publishes to the
   master catalog. Nothing lands without her sign-off.
6. **Measure** — a running counter of items processed, founder hours saved and cost
   avoided, with the assumptions shown on screen.

---

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Demo path (about 3 minutes)

1. **Onboard a Supplier** → pick **Bay State Seafood Co.** — the broken CSV. Point out
   the banner rows, the mixed `,`/`;` delimiters, the `"$22,50"` decimal-comma typo and
   the shrimp with no price.
2. Hit **Run the Catalog Engineer**. Seven clean rows in ~2 seconds against 21 minutes
   of manual keying.
3. Show **What it cleaned up**, then the amber flag on the shrimp — the tool asks
   rather than guesses.
4. Type a price into the editor, then **Publish**.
5. Repeat with **Green Valley Farms** (an unstructured phone note) to show it is not
   one hardcoded trick.
6. **Master Catalog** → one clean, searchable, exportable catalog from three suppliers
   who each sent a different mess.
7. **ROI Dashboard** → hours saved, share of the 4-hour daily bottleneck reclaimed, and
   the annualised projection.

---

## How the extraction works

The three demo suppliers return **hardcoded** clean output. This is deliberate: it makes
the live demo deterministic, and it is labeled in the code
([mock_data.py](mock_data.py)) rather than hidden.

Anything **pasted by hand** runs through a real rule-based parser — regex price
extraction with decimal-comma repair, junk-line filtering, keyword category inference
and phrase-based bulk-availability detection. The UI says when that path is used, so
nothing on screen claims to be more than it is.

Swapping in a live LLM call is a single function: `extract_catalog()` in
[mock_data.py](mock_data.py) already returns the `(DataFrame, metadata)` shape the UI
expects. Nothing in [app.py](app.py) changes.

---

## ROI math

| Input | Value |
| --- | --- |
| Manual keying time per item | 3 minutes |
| Founder time currently lost per day | 4 hours |
| Founder hourly value | $65 (adjustable in the sidebar) |

Hours saved = `items × 3 ÷ 60`. Cost avoided = `hours × hourly rate`. Every assumption is
on screen and adjustable — the judges can re-run the numbers against their own.

---

## Files

| File | Purpose |
| --- | --- |
| [app.py](app.py) | Streamlit UI — onboarding flow, master catalog, ROI dashboard |
| [mock_data.py](mock_data.py) | Demo fixtures, catalog schema, extraction pipeline |
| [requirements.txt](requirements.txt) | `streamlit`, `pandas` |
