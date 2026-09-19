# The Supply Chain Expediter

**AINU Misneach 2026 — Track 01:** build the hire an early founder can't afford yet.

Supplier delay email in. A costed, sourceable recovery plan out — built on **live
distributor data**, not invented numbers.

---

## Founder Persona

An **early-stage hardware / robotics founder** running a small pilot production
line. No procurement hire, no supply chain analyst, no ERP.

## The Bottleneck

**Component shortages.** A supplier emails to say a part has slipped 22 weeks.
That one email costs the founder half a day: find the part number, check stock at
every distributor, compare factory lead times, price the alternates, work out
whether any of it actually beats waiting.

They do this by hand, across a dozen browser tabs, every time a supplier slips.

## The Hire

The Expediter is the procurement analyst they'd hire if they could. It reads the
email, resolves the real parts against live distributor data, and returns a ranked
recovery plan with the downtime cost attached.

---

## What makes it real

Everything on the sourcing table is **live from the Nexar API** (Altium/Octopart):

| Field | Source |
| --- | --- |
| Part identity, manufacturer, category | Nexar, live |
| Distributor stock levels | Nexar, live |
| Factory lead times | Nexar, live |
| Price breaks at your order quantity | Nexar, live |
| Qualified alternates | Nexar similar-parts graph, live |
| Inbound shipping transit | **Modelled estimate** — labelled as such in the UI |

The API also does the hardest parsing job. The email parser extracts candidate
part numbers liberally, then hands every candidate to Nexar — whatever Nexar
recognises is a real part, and the rest is discarded. Live data is the filter,
which is why `22WKS` never reaches the sourcing table.

---

## Setup

### 1. Get Nexar credentials

1. Sign in at [portal.nexar.com](https://portal.nexar.com)
2. **Applications → Create application**
3. Enable the **Supply** scope
4. Copy the **Client ID** and **Client Secret**

### 2. Give them to the app

Any one of these — the app checks in this order:

```bash
# Option A - paste them into the sidebar at runtime (nothing to configure)

# Option B - environment variables
set NEXAR_CLIENT_ID=your-id
set NEXAR_CLIENT_SECRET=your-secret

# Option C - copy .streamlit/secrets.toml.example to .streamlit/secrets.toml
```

`.streamlit/secrets.toml` and `.env` are gitignored. Credentials are never
hardcoded and never logged.

### 3. Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Demo path (about 3 minutes)

1. Sidebar → **Connect to Nexar**. The status goes green; the live-call counter
   starts at zero. This is the moment to say the data is real.
2. **Expedite a Delay** → the Meridian email. Two part numbers buried in prose,
   only one of them actually delayed. Read the line about the 22-week lead time.
3. **Run the Expediter.** Watch the status: candidates found → resolved against
   Nexar → live stock and pricing → alternates.
4. The payoff: *waiting puts parts on the line in February. Digi-Key puts them
   there tomorrow. That's 153 days of downtime avoided.*
5. Point at the **discarded tokens** line — the live lookup is what separates a
   part number from a word.
6. Scroll to **alternates** — pulled from Nexar's similar-parts graph, each one
   re-checked for its own stock and lead time.
7. **Save the plan**, then **ROI Dashboard** for the cumulative figure.

**If anything goes wrong mid-demo, nothing breaks.** See below.

---

## The fallback

The demo cannot die on stage. If the live lookup fails for any reason — no
credentials, exhausted quota, rate limit, dead wifi, timeout, an empty response,
or an unhandled crash in the transport — the app silently falls back to a
snapshot in [offline_data.py](offline_data.py) and keeps going. The pipeline is
identical; only the data source changes.

What it will **not** do is pass snapshot figures off as live data. Every offline
result carries a banner naming the mode and the exact reason it downgraded:

> **Offline snapshot — these are representative figures, not live distributor
> data.** Reason: You have exceeded your part limit of 0.

Saved plans record which source produced them, so the ROI table never mixes the
two silently. If a judge asks whether the numbers are real, the app has already
answered.

All seven failure paths are covered by tests (`fallback_test.py`): missing
client, quota wall, network failure, rate limit, unexpected exception, empty
response, and the working-API case that must still say "live".

---

## ROI math

| Input | Value |
| --- | --- |
| Line downtime cost | $2,500/day (adjustable in the sidebar) |
| Supplier delay | parsed from the email |
| Recovery time | live stock + modelled transit |

`days saved = supplier delay − recovery time`
`value protected = days saved × downtime cost`

Every input is on screen and adjustable, so judges can re-run the numbers against
their own assumptions.

---

## Files

| File | Purpose |
| --- | --- |
| [app.py](app.py) | Streamlit UI — expedite flow, saved plans, ROI dashboard |
| [nexar_client.py](nexar_client.py) | OAuth2 token caching + batched GraphQL queries |
| [expediter.py](expediter.py) | Email parsing, sourcing options, ranking, ROI |
| [demo_emails.py](demo_emails.py) | Three realistic delay notices using real MPNs |
| [requirements.txt](requirements.txt) | `streamlit`, `pandas`, `requests` |

---

## API efficiency

A full recovery plan costs **two** Nexar calls, regardless of how many parts the
email mentions: one `supMultiMatch` batching every candidate MPN, and one more
batching the alternates. Tokens are cached in-process for their full 24-hour
lifetime, as Nexar's own guidance asks.
