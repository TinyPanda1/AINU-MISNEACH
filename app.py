"""
The Catalog Engineer
====================
AINU Misneach 2026 - Track 01

The hire an early founder cannot afford yet: a catalog operations associate
who turns messy supplier submissions into a clean, database-ready catalog.

Run with:  streamlit run app.py
"""

import time

import pandas as pd
import streamlit as st

from mock_data import (
    BULK_OPTIONS,
    CATEGORIES,
    DEFAULT_HOURLY_RATE,
    MANUAL_HOURS_PER_DAY,
    MINUTES_SAVED_PER_ITEM,
    PIPELINE_STAGES,
    SAMPLES,
    SCHEMA_COLUMNS,
    empty_catalog,
    extract_catalog,
)

PERSONA = "Non-technical solo founder of a B2B wholesale marketplace for local restaurants"
BOTTLENECK = (
    "Supplier onboarding. Suppliers send inventory as messy emails, broken CSVs and "
    "pasted notes. The founder loses ~4 hours a day retyping them into a clean schema."
)

st.set_page_config(
    page_title="The Catalog Engineer",
    page_icon=":package:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; }
      .ce-hero {
        background: linear-gradient(120deg, #0f2a44 0%, #1b4965 55%, #2a6f97 100%);
        color: #fff; padding: 1.4rem 1.6rem; border-radius: 14px; margin-bottom: 1.2rem;
      }
      .ce-hero h1 { margin: 0 0 .25rem 0; font-size: 1.9rem; letter-spacing: -.02em; }
      .ce-hero p  { margin: 0; opacity: .88; font-size: .97rem; }
      .ce-badge {
        display: inline-block; background: rgba(255,255,255,.16); border-radius: 999px;
        padding: .18rem .7rem; font-size: .72rem; letter-spacing: .09em;
        text-transform: uppercase; margin-bottom: .55rem;
      }
      .ce-label {
        font-size: .7rem; letter-spacing: .1em; text-transform: uppercase;
        color: #6b7b8c; font-weight: 700; margin-bottom: .3rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("catalog", empty_catalog())
    ss.setdefault("suppliers", [])       # names of onboarded suppliers
    ss.setdefault("runs", [])            # {supplier, items, seconds}
    ss.setdefault("pending", None)       # staged extraction awaiting approval
    ss.setdefault("hourly_rate", DEFAULT_HOURLY_RATE)


init_state()


# --------------------------------------------------------------------------
# ROI helpers - the math is deliberately simple so judges can audit it
# --------------------------------------------------------------------------
def roi_figures():
    items = int(len(st.session_state.catalog))
    minutes = items * MINUTES_SAVED_PER_ITEM
    hours = minutes / 60.0
    dollars = hours * st.session_state.hourly_rate
    days_reclaimed = hours / MANUAL_HOURS_PER_DAY if MANUAL_HOURS_PER_DAY else 0.0
    return {
        "items": items,
        "minutes": minutes,
        "hours": hours,
        "dollars": dollars,
        "days_reclaimed": days_reclaimed,
    }


def hero():
    st.markdown(
        """
        <div class="ce-hero">
          <div class="ce-badge">AINU Misneach 2026 &middot; Track 01</div>
          <h1>The Catalog Engineer</h1>
          <p>The catalog operations hire an early founder cannot afford yet &mdash;
             messy supplier inventory in, clean database rows out.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def eligibility_panel():
    """Persona + bottleneck, shown on every page - Track 01 requires both be named."""
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown('<div class="ce-label">Founder Persona</div>', unsafe_allow_html=True)
            st.write(PERSONA)
    with right:
        with st.container(border=True):
            st.markdown('<div class="ce-label">The Bottleneck</div>', unsafe_allow_html=True)
            st.write(BOTTLENECK)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### :package: The Catalog Engineer")
    st.caption("Your first catalog ops hire.")
    page = st.radio(
        "Go to",
        ["Onboard a Supplier", "Master Catalog", "ROI Dashboard"],
        label_visibility="collapsed",
    )

    st.divider()
    figures = roi_figures()
    st.markdown('<div class="ce-label">Live Savings Counter</div>', unsafe_allow_html=True)
    st.metric("Items processed", "{:,}".format(figures["items"]))
    st.metric("Founder hours saved", "{:.1f} h".format(figures["hours"]))
    st.metric("Cost avoided", "${:,.0f}".format(figures["dollars"]))

    st.divider()
    st.session_state.hourly_rate = st.slider(
        "Founder hourly value ($)", 25, 200, st.session_state.hourly_rate, step=5,
        help="Used only for the cost-avoided figure on the ROI dashboard.",
    )
    st.caption("Assumes {} minutes of manual keying saved per catalog item.".format(MINUTES_SAVED_PER_ITEM))

    if st.session_state.suppliers:
        st.divider()
        st.markdown('<div class="ce-label">Onboarded</div>', unsafe_allow_html=True)
        for name in st.session_state.suppliers:
            st.write("- {}".format(name))


# ==========================================================================
# PAGE 1 - Onboard a Supplier
# ==========================================================================
def page_onboard():
    hero()
    eligibility_panel()
    st.write("")

    st.subheader("1. Drop in whatever the supplier sent you")
    st.caption("No formatting, no template, no cleanup. Forward the email or paste the text.")

    mode = st.radio(
        "Input source",
        ["Use a demo supplier", "Paste my own text"],
        horizontal=True,
        label_visibility="collapsed",
    )

    sample_id, raw_text, supplier_name = None, "", "Pasted input"

    if mode == "Use a demo supplier":
        labels = ["{}  -  {}".format(s["supplier"], s["source"]) for s in SAMPLES]
        choice = st.selectbox("Pick an inbound supplier submission", labels)
        sample = SAMPLES[labels.index(choice)]
        sample_id, raw_text, supplier_name = sample["id"], sample["raw"], sample["supplier"]
        st.info("**{}** - {}".format(sample["contact"], sample["blurb"]), icon=":material/mail:")
        st.text_area("Raw inbound submission", raw_text, height=300, disabled=True)
    else:
        raw_text = st.text_area(
            "Paste a supplier's inventory list",
            height=300,
            placeholder="Paste an email, a broken CSV, or a note. One product per line works best.",
        )
        st.caption(
            "Pasted text runs through the rule-based parser, not the scripted demo path - "
            "results will be rougher and may need edits below."
        )

    run = st.button(
        "Run the Catalog Engineer",
        type="primary",
        width="stretch",
        disabled=not str(raw_text).strip(),    )

    if run:
        started = time.perf_counter()
        with st.status("Catalog Engineer is working...", expanded=True) as status:
            for label, delay in PIPELINE_STAGES:
                st.write(label)
                time.sleep(delay)
            df, meta = extract_catalog(raw_text, sample_id)
            status.update(
                label="Extracted {} items from {}".format(len(df), supplier_name),
                state="complete",
                expanded=False,
            )
        st.session_state.pending = {
            "df": df,
            "meta": meta,
            "supplier": supplier_name,
            "raw": raw_text,
            "seconds": round(time.perf_counter() - started, 1),
        }
        st.rerun()

    pending = st.session_state.pending
    if not pending:
        return

    df, meta = pending["df"], pending["meta"]
    st.divider()

    st.success(
        "Extracted **{} clean items** from {} in **{} seconds**.".format(
            len(df), pending["supplier"], pending["seconds"]
        ),
        icon=":material/task_alt:",
    )
    if meta["mode"] == "heuristic":
        st.caption("Parsed by the rule-based fallback, not the scripted demo path.")

    manual_minutes = len(df) * MINUTES_SAVED_PER_ITEM
    a, b, c = st.columns(3)
    a.metric("Items extracted", len(df))
    b.metric("Manual keying time", "{} min".format(manual_minutes))
    c.metric("Catalog Engineer", "{} sec".format(pending["seconds"]),
             delta="-{} min".format(manual_minutes), delta_color="inverse")

    st.subheader("2. What it cleaned up")
    with st.container(border=True):
        for fix in meta["fixes"]:
            st.write("- {}".format(fix))

    for note in meta["review"]:
        st.warning(note, icon=":material/edit_note:")

    st.subheader("3. Review and adjust, then publish")
    st.caption("Every row is editable. Nothing reaches your catalog until you approve it.")

    edited = st.data_editor(
        df,
        key="editor_{}".format(pending["supplier"]),
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "SKU": st.column_config.TextColumn(
                "SKU", width="medium", help="Generated where the supplier gave none."),
            "Item_Name": st.column_config.TextColumn("Item Name", width="large"),
            "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, width="medium"),
            "Unit_Price": st.column_config.NumberColumn(
                "Unit Price", format="$%.2f", min_value=0.0, step=0.05),
            "Bulk_Availability": st.column_config.SelectboxColumn(
                "Bulk Availability", options=BULK_OPTIONS, width="medium"),
        },
    )

    save, discard = st.columns([3, 1])
    with save:
        if st.button("Publish {} items to my catalog".format(len(edited)),
                     type="primary", width="stretch"):
            commit_to_catalog(edited, pending)
            st.rerun()
    with discard:
        if st.button("Discard", width="stretch"):
            st.session_state.pending = None
            st.rerun()


def commit_to_catalog(edited, pending):
    """Merge an approved extraction into the master catalog, de-duplicating by SKU."""
    clean = edited.copy()
    clean["Unit_Price"] = pd.to_numeric(clean["Unit_Price"], errors="coerce")
    clean = clean.dropna(subset=["Item_Name"])

    current = st.session_state.catalog
    merged = clean if current.empty else pd.concat([current, clean], ignore_index=True)
    merged = merged.drop_duplicates(subset=["SKU"], keep="last").reset_index(drop=True)

    st.session_state.catalog = merged[SCHEMA_COLUMNS]
    if pending["supplier"] not in st.session_state.suppliers:
        st.session_state.suppliers.append(pending["supplier"])
    st.session_state.runs.append({
        "supplier": pending["supplier"],
        "items": int(len(clean)),
        "seconds": pending["seconds"],
    })
    st.session_state.pending = None
    st.toast("{} items published to your catalog.".format(len(clean)), icon=":material/inventory_2:")
    st.balloons()


# ==========================================================================
# PAGE 2 - Master Catalog
# ==========================================================================
def page_catalog():
    hero()
    catalog = st.session_state.catalog

    if catalog.empty:
        st.info("Your catalog is empty. Onboard a supplier to populate it.", icon=":material/inventory_2:")
        return

    priced = catalog["Unit_Price"].dropna()
    a, b, c, d = st.columns(4)
    a.metric("Items in catalog", len(catalog))
    b.metric("Suppliers onboarded", len(st.session_state.suppliers))
    c.metric("Categories covered", catalog["Category"].nunique())
    d.metric("Median unit price", "${:,.2f}".format(priced.median()) if len(priced) else "n/a")

    missing = int(catalog["Unit_Price"].isna().sum())
    if missing:
        st.warning("{} item(s) still need a price before they can go live.".format(missing),
                   icon=":material/price_check:")

    st.subheader("Catalog composition")
    breakdown = (
        catalog.groupby("Category")
        .agg(Items=("SKU", "count"), Avg_Price=("Unit_Price", "mean"))
        .reset_index()
        .sort_values("Items", ascending=False)
    )
    st.dataframe(
        breakdown,
        hide_index=True,
        width="stretch",
        column_config={
            "Category": st.column_config.TextColumn("Category", width="medium"),
            "Items": st.column_config.ProgressColumn(
                "Items", format="%d", min_value=0, max_value=int(breakdown["Items"].max())),
            "Avg_Price": st.column_config.NumberColumn("Avg Unit Price", format="$%.2f"),
        },
    )

    st.subheader("Full catalog")
    search = st.text_input("Filter by name, SKU or category", placeholder="e.g. salmon, GVF, Produce")
    view = catalog
    if search.strip():
        needle = search.strip().lower()
        view = catalog[
            catalog["Item_Name"].str.lower().str.contains(needle, na=False)
            | catalog["SKU"].str.lower().str.contains(needle, na=False)
            | catalog["Category"].str.lower().str.contains(needle, na=False)
        ]
        st.caption("{} of {} items match.".format(len(view), len(catalog)))

    st.dataframe(
        view,
        hide_index=True,
        width="stretch",
        column_config={
            "Unit_Price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
            "Item_Name": st.column_config.TextColumn("Item Name", width="large"),
        },
    )

    st.download_button(
        "Download catalog as CSV",
        catalog.to_csv(index=False).encode("utf-8"),
        file_name="catalog.csv",
        mime="text/csv",
        width="stretch",
    )


# ==========================================================================
# PAGE 3 - ROI Dashboard
# ==========================================================================
def page_roi():
    hero()
    eligibility_panel()
    st.write("")

    figures = roi_figures()
    if not figures["items"]:
        st.info("Onboard a supplier to start the savings counter.", icon=":material/monitoring:")
        return

    st.subheader("Estimated time and cost saved")
    a, b, c, d = st.columns(4)
    a.metric("Items processed", "{:,}".format(figures["items"]))
    b.metric("Minutes saved", "{:,}".format(figures["minutes"]))
    c.metric("Founder hours saved", "{:.1f} h".format(figures["hours"]))
    d.metric("Cost avoided", "${:,.0f}".format(figures["dollars"]))

    st.caption(
        "Math: {items} items x {rate} min of manual keying = {mins} min. "
        "Valued at ${hourly}/hour of founder time.".format(
            items=figures["items"], rate=MINUTES_SAVED_PER_ITEM,
            mins=figures["minutes"], hourly=st.session_state.hourly_rate,
        )
    )

    st.subheader("Against the {}-hour-a-day bottleneck".format(MANUAL_HOURS_PER_DAY))
    share = min(figures["days_reclaimed"], 1.0)
    st.progress(share)
    st.write(
        "This session reclaimed **{:.1f} hours** - about **{:.0%}** of one full day "
        "previously lost to supplier onboarding.".format(figures["hours"], share)
    )

    if st.session_state.runs:
        st.subheader("Per-supplier breakdown")
        runs = pd.DataFrame(st.session_state.runs)
        runs["Manual_Minutes"] = runs["items"] * MINUTES_SAVED_PER_ITEM
        runs["Engineer_Seconds"] = runs["seconds"]
        runs["Minutes_Saved"] = runs["Manual_Minutes"] - (runs["seconds"] / 60.0)
        display = runs[["supplier", "items", "Manual_Minutes", "Engineer_Seconds", "Minutes_Saved"]]
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_config={
                "supplier": st.column_config.TextColumn("Supplier", width="large"),
                "items": st.column_config.NumberColumn("Items"),
                "Manual_Minutes": st.column_config.NumberColumn("Manual (min)", format="%d"),
                "Engineer_Seconds": st.column_config.NumberColumn("Engineer (sec)", format="%.1f"),
                "Minutes_Saved": st.column_config.NumberColumn("Minutes saved", format="%.1f"),
            },
        )

    st.subheader("Annualised, at this pace")
    weekly_suppliers = st.number_input(
        "Suppliers onboarded per week", min_value=1, max_value=200, value=5,
        help="Adjust to match the founder's real pipeline.",
    )
    avg_items = figures["items"] / max(len(st.session_state.runs), 1)
    annual_items = weekly_suppliers * avg_items * 52
    annual_hours = annual_items * MINUTES_SAVED_PER_ITEM / 60.0
    annual_dollars = annual_hours * st.session_state.hourly_rate

    x, y, z = st.columns(3)
    x.metric("Items / year", "{:,.0f}".format(annual_items))
    y.metric("Hours / year", "{:,.0f} h".format(annual_hours))
    z.metric("Cost avoided / year", "${:,.0f}".format(annual_dollars))
    st.caption(
        "Based on an average of {:.0f} items per supplier observed in this session.".format(avg_items)
    )


PAGES = {
    "Onboard a Supplier": page_onboard,
    "Master Catalog": page_catalog,
    "ROI Dashboard": page_roi,
}
PAGES[page]()
