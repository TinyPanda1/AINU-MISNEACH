"""
The Supply Chain Expediter
==========================
AINU Misneach 2026 - Track 01

The hire an early hardware founder cannot afford yet: a supply chain analyst who
reads a supplier delay email and comes back with a costed recovery plan built on
live distributor data.

Run with:  streamlit run app.py
"""

import time
from datetime import date

import pandas as pd
import streamlit as st

from demo_emails import DEMO_EMAILS
from expediter import (
    DEFAULT_DOWNTIME_COST_PER_DAY,
    eta_date,
    extract_delay_days,
    extract_mpn_candidates,
    extract_quantity,
    format_date,
    part_summary,
    recovery_roi,
)
from compare import DEFAULT_WEIGHTS, compare_parts, verdict
from nexar_client import NexarClient, NexarError, resolve_credentials
from offline_data import SNAPSHOT_LABEL, offline_match, offline_search

PERSONA = (
    "Early-stage hardware / robotics founder running a small pilot production line, "
    "with no procurement or supply chain hire."
)
BOTTLENECK = (
    "Component shortages. When a supplier emails a delay, the founder loses hours "
    "cross-referencing alternate part databases, distributor stock and factory lead "
    "times by hand to work out how to keep the assembly line running."
)

st.set_page_config(
    page_title="The Supply Chain Expediter",
    page_icon=":material/conveyor_belt:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; }
      .sx-hero {
        background: linear-gradient(120deg, #131a2b 0%, #1f3a5f 55%, #2d6ca8 100%);
        color: #fff; padding: 1.4rem 1.6rem; border-radius: 14px; margin-bottom: 1.2rem;
      }
      .sx-hero h1 { margin: 0 0 .25rem 0; font-size: 1.9rem; letter-spacing: -.02em; }
      .sx-hero p  { margin: 0; opacity: .88; font-size: .97rem; }
      .sx-badge {
        display: inline-block; background: rgba(255,255,255,.16); border-radius: 999px;
        padding: .18rem .7rem; font-size: .72rem; letter-spacing: .09em;
        text-transform: uppercase; margin-bottom: .55rem;
      }
      .sx-label {
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
    ss.setdefault("client", None)
    ss.setdefault("cred_source", None)
    ss.setdefault("connect_error", None)
    ss.setdefault("pending", None)
    ss.setdefault("plans", [])
    ss.setdefault("downtime_cost", DEFAULT_DOWNTIME_COST_PER_DAY)
    ss.setdefault("api_calls", 0)
    ss.setdefault("max_alternates", 4)
    ss.setdefault("search_result", None)
    ss.setdefault("search_weights", dict(DEFAULT_WEIGHTS))


init_state()


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def fmt_money(value, currency="USD"):
    if value is None:
        return "-"
    symbol = "$" if currency in ("USD", None, "") else ""
    return "{}{:,.4f}".format(symbol, value).rstrip("0").rstrip(".") if value < 1 else \
        "{}{:,.2f}".format(symbol, value)


def fmt_days(value):
    if value is None:
        return "unknown"
    if value == 0:
        return "same day"
    return "{} d".format(int(value))


def hero():
    st.markdown(
        """
        <div class="sx-hero">
          <div class="sx-badge">AINU Misneach 2026 &middot; Track 01</div>
          <h1>The Supply Chain Expediter</h1>
          <p>Supplier delay email in &mdash; a costed, sourceable recovery plan out,
             built on live distributor stock and pricing.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def eligibility_panel():
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown('<div class="sx-label">Founder Persona</div>', unsafe_allow_html=True)
        st.write(PERSONA)
    with right, st.container(border=True):
        st.markdown('<div class="sx-label">The Bottleneck</div>', unsafe_allow_html=True)
        st.write(BOTTLENECK)


# --------------------------------------------------------------------------
# Nexar connection panel
# --------------------------------------------------------------------------
def connect(client_id, client_secret, source):
    try:
        client = NexarClient(client_id, client_secret)
        client.check_connection()
    except NexarError as exc:
        st.session_state.client = None
        st.session_state.connect_error = str(exc)
        return False
    st.session_state.client = client
    st.session_state.cred_source = source
    st.session_state.connect_error = None
    return True


def nexar_sidebar():
    st.markdown('<div class="sx-label">Live Data Source</div>', unsafe_allow_html=True)

    if st.session_state.client is not None:
        client = st.session_state.client
        st.success("Connected to Nexar", icon=":material/cloud_done:")
        st.caption("Credentials from {}.".format(st.session_state.cred_source))
        billed = getattr(client, "parts_billed", 0)
        hits = getattr(client, "cache_hits", 0)
        st.caption(
            "API calls: {} | parts billed to quota: {} | served from cache: {}".format(
                st.session_state.api_calls, billed, hits)
        )
        if hits:
            st.caption("Re-running a demo costs nothing - cached parts are never re-billed.")
        if st.button("Disconnect", width="stretch"):
            st.session_state.client = None
            st.session_state.cred_source = None
            st.rerun()
        return

    found_id, found_secret, source = resolve_credentials()
    if found_id and found_secret:
        st.info("Found credentials in {}.".format(source), icon=":material/key:")
        if st.button("Connect to Nexar", type="primary", width="stretch"):
            if connect(found_id, found_secret, source):
                st.rerun()
    else:
        st.warning("Not connected - no live data.", icon=":material/cloud_off:")
        st.caption("Create an app with the **Supply** scope at portal.nexar.com, then paste its credentials.")

    with st.expander("Paste credentials", expanded=not bool(found_id)):
        cid = st.text_input("Client ID", key="cid_input")
        secret = st.text_input("Client Secret", type="password", key="secret_input")
        if st.button("Connect", width="stretch", disabled=not (cid and secret)):
            if connect(cid, secret, "pasted into the sidebar"):
                st.rerun()

    if st.session_state.connect_error:
        st.error(st.session_state.connect_error, icon=":material/error:")


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### :material/conveyor_belt: Supply Chain Expediter")
    st.caption("Your first procurement hire.")
    page = st.radio(
        "Go to",
        ["Expedite a Delay", "Part Search & Compare", "Saved Recovery Plans",
         "ROI Dashboard"],
        label_visibility="collapsed",
    )

    st.divider()
    nexar_sidebar()

    st.divider()
    st.markdown('<div class="sx-label">Assumptions</div>', unsafe_allow_html=True)
    st.session_state.downtime_cost = st.number_input(
        "Line downtime cost ($/day)",
        min_value=100, max_value=100_000,
        value=st.session_state.downtime_cost, step=250,
        help="What one idle day on the pilot line costs. Drives the ROI figure.",
    )
    st.session_state.max_alternates = st.slider(
        "Alternates to check per run", 2, 6, st.session_state.max_alternates,
        help="Each alternate counts one part against your Nexar quota. Lower it to "
             "conserve evaluation parts while rehearsing.",
    )
    st.caption(
        "Stock, pricing, lead times and alternates are live from Nexar. "
        "Inbound shipping transit is a modelled estimate, not API data."
    )


# ==========================================================================
# The pipeline
# ==========================================================================
def resolve_parts(mpns, client):
    """
    Live Nexar first, offline snapshot second.

    Returns (resolved, mode, reason). The demo must never die on a network
    blip, a quota wall or dead venue wifi - but it must also never quietly
    pass snapshot numbers off as live distributor data, so every downgrade
    carries the reason it happened and the UI prints it.
    """
    if client is None:
        return offline_match(mpns), "offline", "Not connected to Nexar."

    try:
        resolved = client.match_mpns(mpns)
        st.session_state.api_calls += 1
    except NexarError as exc:
        return offline_match(mpns), "offline", str(exc)
    except Exception as exc:  # transport, JSON, anything unforeseen
        return offline_match(mpns), "offline", "Unexpected error: {}".format(exc)

    # A live call that comes back empty is still a failed demo. Fall back only
    # when the snapshot actually knows these parts, so genuinely unknown MPNs
    # are still reported honestly as unknown.
    if not resolved:
        snapshot = offline_match(mpns)
        if snapshot:
            return snapshot, "offline", "Nexar returned no matches for these part numbers."
    return resolved, "live", None


def search_catalogue(query, client, limit=6):
    """Free-text part search, live first and snapshot second. Same contract as resolve_parts."""
    if client is None:
        return offline_search(query, limit), "offline", "Not connected to Nexar."
    try:
        results = client.search_parts(query, limit=limit)
        st.session_state.api_calls += 1
    except NexarError as exc:
        return offline_search(query, limit), "offline", str(exc)
    except Exception as exc:
        return offline_search(query, limit), "offline", "Unexpected error: {}".format(exc)

    if not results:
        snapshot = offline_search(query, limit)
        if snapshot:
            return snapshot, "offline", "Nexar returned no matches for that search."
    return results, "live", None


def run_expediter(raw_text, client):
    """Parse the email, resolve every candidate against Nexar, rank the options."""
    started = time.perf_counter()
    result = {"raw": raw_text, "errors": []}

    with st.status("Expediter is working...", expanded=True) as status:
        st.write("Reading the delay notice...")
        candidates = extract_mpn_candidates(raw_text)
        quantity = extract_quantity(raw_text)
        delay_days, delay_desc = extract_delay_days(raw_text)
        time.sleep(0.25)

        if not candidates:
            status.update(label="No part numbers found in that message", state="error")
            result["errors"].append(
                "No part numbers were recognised. Paste a message that quotes an MPN."
            )
            return result

        st.write("Found {} candidate part number(s): {}".format(
            len(candidates), ", ".join(candidates)))

        st.write("Resolving against Nexar...")
        resolved, mode, reason = resolve_parts(candidates, client)
        if mode == "offline":
            st.write("Live lookup unavailable - falling back to the offline snapshot.")

        if not resolved:
            status.update(label="No part numbers could be resolved", state="error")
            result["errors"].append(
                "Neither Nexar nor the offline snapshot recognised any of: {}. They "
                "may be internal part numbers rather than manufacturer MPNs.".format(
                    ", ".join(candidates))
            )
            if reason:
                result["errors"].append(reason)
            return result

        rejected = [c for c in candidates if c not in resolved]
        st.write("Confirmed {} real part(s); discarded {} non-part token(s).".format(
            len(resolved), len(rejected)))

        st.write("Pulling live stock, pricing and lead times...")
        summaries = {
            mpn: part_summary(part, quantity)
            for mpn, part in resolved.items()
        }

        # The delayed part is the one the email is actually about - first
        # confirmed MPN in reading order.
        primary_mpn = next((c for c in candidates if c in summaries), None)
        primary = summaries.get(primary_mpn)

        st.write("Checking alternates...")
        alternates = {}
        if primary and primary["similar"]:
            alt_mpns = [s["mpn"] for s in primary["similar"][:st.session_state.max_alternates]]
            alt_parts, alt_mode, alt_reason = resolve_parts(alt_mpns, client)
            alternates = {
                mpn: part_summary(part, quantity)
                for mpn, part in alt_parts.items()
            }
            if alt_mode == "offline":
                mode = "offline"
                reason = reason or alt_reason

        status.update(
            label="{} plan ready for {}".format(
                "Live" if mode == "live" else "Offline",
                primary_mpn or "the order"),
            state="complete", expanded=False,
        )

    result.update({
        "mode": mode,
        "mode_reason": reason,
        "candidates": candidates,
        "rejected": rejected,
        "quantity": quantity,
        "delay_days": delay_days,
        "delay_desc": delay_desc,
        "summaries": summaries,
        "primary_mpn": primary_mpn,
        "alternates": alternates,
        "seconds": round(time.perf_counter() - started, 1),
    })
    return result


# ==========================================================================
# Rendering
# ==========================================================================
def options_frame(options):
    rows = []
    for opt in options:
        rows.append({
            "Distributor": opt["distributor"],
            "In stock": opt["stock"],
            "Covers order": "Yes" if opt["covers_order"] else "No",
            "Factory lead": opt["factory_lead_days"],
            "Transit": opt["transit_days"],
            "Days to line": opt["days_to_line"],
            "Unit price": opt["unit_price"],
            "Order total": opt["total_cost"],
            "MOQ": opt["moq"] or None,
        })
    return pd.DataFrame(rows)


def render_options(options, caption=None):
    if not options:
        st.info("No distributor offers returned for this part.", icon=":material/inventory:")
        return
    frame = options_frame(options)
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            "Distributor": st.column_config.TextColumn(width="medium"),
            "In stock": st.column_config.NumberColumn(format="%d"),
            "Factory lead": st.column_config.NumberColumn("Factory lead (d)", format="%d"),
            "Transit": st.column_config.NumberColumn("Transit (d)", format="%d"),
            "Days to line": st.column_config.NumberColumn("Days to line", format="%d"),
            "Unit price": st.column_config.NumberColumn(format="$%.4f"),
            "Order total": st.column_config.NumberColumn(format="$%.2f"),
            "MOQ": st.column_config.NumberColumn(format="%d"),
        },
    )
    if caption:
        st.caption(caption)


def render_result(result):
    if result.get("errors") and not result.get("summaries"):
        for err in result["errors"]:
            st.error(err, icon=":material/error:")
        return

    quantity = result["quantity"]
    primary = result["summaries"].get(result["primary_mpn"])
    if primary is None:
        st.error("Could not identify the delayed part.", icon=":material/error:")
        return

    # Never let snapshot figures read as live distributor data.
    if result.get("mode") == "live":
        st.success(
            "Resolved **{}** against **live Nexar data** in **{} seconds**.".format(
                primary["mpn"], result["seconds"]),
            icon=":material/cloud_done:",
        )
    else:
        st.warning(
            "**Offline snapshot — these are representative figures, not live "
            "distributor data.** Reason: {}".format(
                result.get("mode_reason") or "live lookup unavailable"),
            icon=":material/cloud_off:",
        )
        st.caption(
            "The pipeline is identical either way. Connect to Nexar in the sidebar "
            "to run the same plan against live stock and pricing."
        )

    for err in result.get("errors", []):
        st.warning(err, icon=":material/warning:")

    # ---- what the email said --------------------------------------------
    st.subheader("1. What the supplier told you")
    a, b, c = st.columns(3)
    a.metric("Delayed part", primary["mpn"])
    b.metric("Quantity", "{:,}".format(quantity))
    c.metric(
        "Supplier ETA",
        result["delay_desc"] or "not stated",
        help="Parsed straight from the email text.",
    )
    st.caption("{} - {} | {}".format(
        primary["manufacturer"], primary["name"] or primary["description"],
        primary["category"] or "uncategorised"))

    if result["rejected"]:
        st.caption("Discarded as non-parts by the live lookup: {}".format(
            ", ".join(result["rejected"])))

    # ---- the recovery plan ----------------------------------------------
    st.subheader("2. The recovery plan")
    best = primary["best"]
    roi = recovery_roi(result["delay_days"], best["days_to_line"] if best else None,
                       st.session_state.downtime_cost)

    if best is None or best["days_to_line"] is None:
        st.warning(
            "No distributor is quoting a usable lead time for {} right now. "
            "The alternates below are the path forward.".format(primary["mpn"]),
            icon=":material/warning:",
        )
    else:
        cols = st.columns(4)
        cols[0].metric("Fastest source", best["distributor"])
        cols[1].metric("Parts on the line in", fmt_days(best["days_to_line"]),
                       help="Distributor stock plus modelled inbound transit.")
        cols[2].metric("Order cost", fmt_money(best["total_cost"]),
                       help="{} x {} at the applicable price break.".format(
                           "{:,}".format(quantity), fmt_money(best["unit_price"])))
        if roi and roi["days_saved"] > 0:
            cols[3].metric("Downtime avoided", "{} d".format(roi["days_saved"]),
                           delta="${:,.0f}".format(roi["dollars_saved"]))
        else:
            cols[3].metric("Downtime avoided", "-")

        if roi and roi["days_saved"] > 0:
            st.success(
                "Waiting on the supplier puts parts on the line around **{}**. "
                "Sourcing from **{}** instead puts them there around **{}** - "
                "**{} days ({} weeks)** of downtime avoided, worth **${:,.0f}** "
                "at ${:,}/day.".format(
                    format_date(eta_date(result["delay_days"])),
                    best["distributor"],
                    format_date(eta_date(best["days_to_line"])),
                    roi["days_saved"], roi["weeks_saved"], roi["dollars_saved"],
                    st.session_state.downtime_cost,
                ),
                icon=":material/savings:",
            )

    st.markdown("**Live distributor offers for {}**".format(primary["mpn"]))
    st.caption("Total stock across all distributors: {:,} units.".format(primary["total_avail"]))
    render_options(
        primary["options"],
        "Stock, factory lead time and price breaks are live from Nexar. "
        "Transit is a modelled estimate.",
    )

    # ---- alternates ------------------------------------------------------
    st.subheader("3. Qualified alternates")
    if not result["alternates"]:
        st.info("Nexar returned no alternates for this part.", icon=":material/alt_route:")
    else:
        rows = []
        for mpn, alt in result["alternates"].items():
            alt_best = alt["best"]
            rows.append({
                "MPN": mpn,
                "Manufacturer": alt["manufacturer"],
                "Total stock": alt["total_avail"],
                "Fastest source": alt_best["distributor"] if alt_best else "-",
                "Days to line": alt_best["days_to_line"] if alt_best else None,
                "Unit price": alt_best["unit_price"] if alt_best else None,
                "Order total": alt_best["total_cost"] if alt_best else None,
            })
        frame = pd.DataFrame(rows).sort_values(
            "Days to line", na_position="last").reset_index(drop=True)
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                "MPN": st.column_config.TextColumn(width="medium"),
                "Total stock": st.column_config.NumberColumn(format="%d"),
                "Days to line": st.column_config.NumberColumn(format="%d"),
                "Unit price": st.column_config.NumberColumn(format="$%.4f"),
                "Order total": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        st.caption(
            "Alternates come from Nexar's similar-parts graph. Confirm pin and "
            "electrical compatibility before substituting - this ranks availability, "
            "not fitness for your design."
        )

        with st.expander("Distributor detail for each alternate"):
            for mpn, alt in result["alternates"].items():
                st.markdown("**{}** - {}".format(mpn, alt["manufacturer"]))
                render_options(alt["options"])

    # ---- other parts in the email ---------------------------------------
    others = {m: s for m, s in result["summaries"].items() if m != result["primary_mpn"]}
    if others:
        st.subheader("4. Other parts mentioned")
        for mpn, summary in others.items():
            with st.expander("{} - {} ({:,} in stock)".format(
                    mpn, summary["manufacturer"], summary["total_avail"])):
                render_options(summary["options"])

    # ---- save ------------------------------------------------------------
    st.divider()
    if st.button("Save this recovery plan", type="primary", width="stretch"):
        st.session_state.plans.append({
            "mpn": primary["mpn"],
            "manufacturer": primary["manufacturer"],
            "quantity": quantity,
            "delay_days": result["delay_days"],
            "best_distributor": best["distributor"] if best else None,
            "days_to_line": best["days_to_line"] if best else None,
            "order_cost": best["total_cost"] if best else None,
            "days_saved": roi["days_saved"] if roi else 0,
            "dollars_saved": roi["dollars_saved"] if roi else 0,
            "data_source": result.get("mode", "offline"),
            "saved_at": date.today().isoformat(),
        })
        st.session_state.pending = None
        st.toast("Recovery plan saved.", icon=":material/bookmark_added:")
        st.balloons()
        st.rerun()


# ==========================================================================
# PAGE 1 - Expedite a Delay
# ==========================================================================
def page_expedite():
    hero()
    eligibility_panel()
    st.write("")

    client = st.session_state.client
    if client is None:
        st.info(
            "Not connected to Nexar — the Expediter will run against its offline "
            "snapshot ({}) and label every result as such. Connect in the sidebar "
            "for live distributor data.".format(SNAPSHOT_LABEL),
            icon=":material/cloud_off:",
        )

    st.subheader("Paste the delay notice")
    st.caption("Forward the supplier's email exactly as it arrived. No template needed.")

    mode = st.radio(
        "Input source",
        ["Use a demo email", "Paste my own"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "Use a demo email":
        labels = [e["label"] for e in DEMO_EMAILS]
        choice = st.selectbox("Inbound message", labels)
        email = DEMO_EMAILS[labels.index(choice)]
        raw_text = email["body"]
        st.info("**{}** - {}".format(email["sender"], email["blurb"]),
                icon=":material/mail:")
        st.text_area("Raw message", raw_text, height=320, disabled=True)
    else:
        raw_text = st.text_area(
            "Paste a supplier delay email",
            height=320,
            placeholder="Paste the email. Anything quoting a manufacturer part number works.",
        )

    if st.button("Run the Expediter", type="primary", width="stretch",
                 disabled=not str(raw_text).strip()):
        st.session_state.pending = run_expediter(raw_text, client)
        st.rerun()

    if st.session_state.pending:
        st.divider()
        render_result(st.session_state.pending)


# ==========================================================================
# PAGE 2 - Saved Recovery Plans
# ==========================================================================
def page_plans():
    hero()
    plans = st.session_state.plans
    if not plans:
        st.info("No saved plans yet. Expedite a delay to create one.",
                icon=":material/bookmark:")
        return

    frame = pd.DataFrame(plans)
    a, b, c = st.columns(3)
    a.metric("Plans saved", len(plans))
    b.metric("Downtime days avoided", int(frame["days_saved"].sum()))
    c.metric("Value protected", "${:,.0f}".format(frame["dollars_saved"].sum()))

    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            "mpn": st.column_config.TextColumn("MPN", width="medium"),
            "manufacturer": st.column_config.TextColumn("Manufacturer"),
            "quantity": st.column_config.NumberColumn("Qty", format="%d"),
            "delay_days": st.column_config.NumberColumn("Supplier delay (d)", format="%d"),
            "best_distributor": st.column_config.TextColumn("Sourced from"),
            "days_to_line": st.column_config.NumberColumn("Days to line", format="%d"),
            "order_cost": st.column_config.NumberColumn("Order cost", format="$%.2f"),
            "days_saved": st.column_config.NumberColumn("Days saved", format="%d"),
            "dollars_saved": st.column_config.NumberColumn("Value protected", format="$%.0f"),
            "saved_at": st.column_config.TextColumn("Saved"),
        },
    )
    st.download_button(
        "Download plans as CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name="recovery_plans.csv",
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

    plans = st.session_state.plans
    if not plans:
        st.info("Save a recovery plan to start the ROI counter.",
                icon=":material/monitoring:")
        return

    frame = pd.DataFrame(plans)
    days_saved = int(frame["days_saved"].sum())
    dollars = float(frame["dollars_saved"].sum())
    spend = float(frame["order_cost"].fillna(0).sum())

    st.subheader("Downtime avoided")
    a, b, c, d = st.columns(4)
    a.metric("Delays expedited", len(plans))
    b.metric("Downtime days avoided", days_saved)
    c.metric("Value protected", "${:,.0f}".format(dollars))
    d.metric("Expedite spend", "${:,.0f}".format(spend))

    st.caption(
        "Value protected = downtime days avoided x ${:,}/day. Every input is on "
        "screen and adjustable in the sidebar.".format(st.session_state.downtime_cost)
    )

    if spend > 0:
        st.subheader("Return on the expedite spend")
        ratio = dollars / spend if spend else 0
        st.metric("Protected per dollar spent", "{:,.1f}x".format(ratio))
        st.progress(min(ratio / 20.0, 1.0))
        st.caption(
            "Spending ${:,.0f} on expedited parts protects ${:,.0f} of production "
            "time.".format(spend, dollars)
        )

    st.subheader("The manual alternative")
    st.write(
        "Each of these plans required cross-referencing distributor stock, factory "
        "lead times and price breaks across multiple sources, then checking "
        "alternates one by one. That is roughly **45-90 minutes per delay** by hand. "
        "The Expediter returns it in **seconds**, against the same live data."
    )
    st.caption("Live Nexar API calls made this session: {}".format(st.session_state.api_calls))


# ==========================================================================
# PAGE - Part Search & Compare
# ==========================================================================
def page_search():
    hero()
    client = st.session_state.client

    st.subheader("Find a part, then find something better")
    st.caption(
        "Paste a part number or describe the product. Every candidate is scored "
        "against your reference part on price, availability, speed and fit."
    )

    if client is None:
        st.info(
            "Not connected to Nexar — searching the offline snapshot ({}). "
            "Connect in the sidebar for the full catalogue.".format(SNAPSHOT_LABEL),
            icon=":material/cloud_off:",
        )

    left, right = st.columns([3, 1])
    with left:
        query = st.text_input(
            "Part number or product",
            placeholder="e.g. DRV8825PWPR, STM32F405, or \"stepper motor driver\"",
        )
    with right:
        quantity = st.number_input("Quantity", min_value=1, max_value=1_000_000,
                                   value=500, step=50)

    cheaper_only = st.toggle(
        "Cheaper alternatives only",
        help="Hide anything that costs more per unit than your reference part.",
    )

    with st.expander("Scoring weights"):
        st.caption(
            "The comparison score is a weighted blend of four sub-scores, each 0-100. "
            "Disagree with the weighting? Change it and the ranking re-sorts."
        )
        w1, w2, w3, w4 = st.columns(4)
        weights = {
            "price": w1.slider("Price", 0.0, 1.0, DEFAULT_WEIGHTS["price"], 0.05),
            "availability": w2.slider("Availability", 0.0, 1.0,
                                      DEFAULT_WEIGHTS["availability"], 0.05),
            "speed": w3.slider("Speed", 0.0, 1.0, DEFAULT_WEIGHTS["speed"], 0.05),
            "fit": w4.slider("Fit", 0.0, 1.0, DEFAULT_WEIGHTS["fit"], 0.05),
        }
        st.session_state.search_weights = weights
        st.caption(
            "Price: 50 = same as reference, 100 = free, 0 = double. "
            "Availability: can one distributor cover your quantity. "
            "Speed: same-day = 100, decaying to 0 at 90 days. "
            "Fit: manufacturer and category match — metadata only, **not** a "
            "pin-compatibility check."
        )

    if st.button("Search", type="primary", width="stretch", disabled=not query.strip()):
        with st.status("Searching...", expanded=True) as status:
            st.write("Looking up \"{}\"...".format(query))
            results, mode, reason = search_catalogue(query, client)

            if not results:
                status.update(label="No parts matched", state="error")
                st.session_state.search_result = {
                    "errors": ["Nothing matched \"{}\". Try a fuller part number.".format(query)],
                    "mode": mode, "mode_reason": reason,
                }
                st.rerun()

            reference = part_summary(results[0], quantity)
            st.write("Reference: {} ({})".format(reference["mpn"], reference["manufacturer"]))

            # Candidates come from two places: the rest of the search hits, and
            # the reference part's own alternates graph.
            candidates = [part_summary(p, quantity) for p in results[1:]]
            if reference["similar"]:
                alt_mpns = [s["mpn"] for s in
                            reference["similar"][:st.session_state.max_alternates]]
                st.write("Pulling {} alternates...".format(len(alt_mpns)))
                alt_parts, alt_mode, alt_reason = resolve_parts(alt_mpns, client)
                known = {c["mpn"] for c in candidates} | {reference["mpn"]}
                for mpn, part in alt_parts.items():
                    if mpn not in known:
                        candidates.append(part_summary(part, quantity))
                if alt_mode == "offline":
                    mode = "offline"
                    reason = reason or alt_reason

            st.write("Scoring {} candidate(s)...".format(len(candidates)))
            status.update(label="Compared {} parts against {}".format(
                len(candidates), reference["mpn"]), state="complete", expanded=False)

        st.session_state.search_result = {
            "reference": reference,
            "candidates": candidates,
            "quantity": quantity,
            "mode": mode,
            "mode_reason": reason,
            "errors": [],
        }
        st.rerun()

    result = st.session_state.get("search_result")
    if not result:
        return

    st.divider()
    for err in result.get("errors", []):
        st.error(err, icon=":material/search_off:")
    if result.get("errors"):
        return

    if result["mode"] == "live":
        st.success("Live Nexar results.", icon=":material/cloud_done:")
    else:
        st.warning(
            "**Offline snapshot — representative figures, not live distributor "
            "data.** Reason: {}".format(result.get("mode_reason") or "unavailable"),
            icon=":material/cloud_off:",
        )

    reference = result["reference"]
    qty = result["quantity"]

    st.subheader("Reference part")
    with st.container(border=True):
        a, b, c, d = st.columns(4)
        a.metric("MPN", reference["mpn"])
        b.metric("Unit price", fmt_money(
            (reference["best"] or {}).get("unit_price") or reference["median_price_1000"]))
        c.metric("Total stock", "{:,}".format(reference["total_avail"]))
        d.metric("Days to line", fmt_days((reference["best"] or {}).get("days_to_line")))
        st.caption("{} — {} | {}".format(
            reference["manufacturer"], reference["name"] or reference["description"],
            reference["category"] or "uncategorised"))

    rows = compare_parts(reference, result["candidates"], qty,
                         weights=st.session_state.get("search_weights"),
                         cheaper_only=cheaper_only)

    st.subheader("Ranked alternatives")
    if not rows:
        st.info(
            "No alternatives to compare." if not cheaper_only else
            "Nothing cheaper than the reference part was found. Turn off the "
            "\"cheaper only\" filter to see the rest.",
            icon=":material/search_off:",
        )
        return

    frame = pd.DataFrame([{
        "Score": r["score"],
        "Verdict": verdict(r),
        "MPN": r["mpn"],
        "Manufacturer": r["manufacturer"],
        "Unit price": r["unit_price"],
        "vs ref": r["savings_pct"],
        "Saved on {:,}".format(qty): r["savings_total"],
        "Stock": r["total_avail"],
        "Days to line": r["days_to_line"],
        "Source": r["distributor"],
    } for r in rows])

    st.dataframe(
        frame, hide_index=True, width="stretch",
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", format="%.0f", min_value=0, max_value=100),
            "Verdict": st.column_config.TextColumn(width="small"),
            "MPN": st.column_config.TextColumn(width="medium"),
            "Unit price": st.column_config.NumberColumn(format="$%.4f"),
            "vs ref": st.column_config.NumberColumn(
                "vs ref", format="%+.1f%%",
                help="Positive means cheaper than your reference part."),
            "Saved on {:,}".format(qty): st.column_config.NumberColumn(format="$%+,.0f"),
            "Stock": st.column_config.NumberColumn(format="%d"),
            "Days to line": st.column_config.NumberColumn(format="%d"),
        },
    )

    best = rows[0]
    if best["savings_total"] and best["savings_total"] > 0:
        st.success(
            "**{}** scores {:.0f}/100 — {:.1f}% cheaper than {}, saving "
            "**${:,.0f}** on {:,} units, on the line in {}.".format(
                best["mpn"], best["score"], best["savings_pct"], reference["mpn"],
                best["savings_total"], qty, fmt_days(best["days_to_line"])),
            icon=":material/savings:",
        )

    with st.expander("How each score was built"):
        breakdown = pd.DataFrame([{
            "MPN": r["mpn"],
            "Price": r["score_price"],
            "Availability": r["score_availability"],
            "Speed": r["score_speed"],
            "Fit": r["score_fit"],
            "Total": r["score"],
        } for r in rows])
        st.dataframe(
            breakdown, hide_index=True, width="stretch",
            column_config={
                col: st.column_config.ProgressColumn(
                    col, format="%.0f", min_value=0, max_value=100)
                for col in ["Price", "Availability", "Speed", "Fit", "Total"]
            },
        )
        st.caption(
            "Fit is inferred from manufacturer and category metadata only. It is "
            "not an electrical or pin-compatibility check — confirm against the "
            "datasheet before substituting anything into a design."
        )


PAGES = {
    "Expedite a Delay": page_expedite,
    "Part Search & Compare": page_search,
    "Saved Recovery Plans": page_plans,
    "ROI Dashboard": page_roi,
}
PAGES[page]()
