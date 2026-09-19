"""
nexar_client.py - live component data from Nexar (Altium / Octopart).

Auth is OAuth2 client-credentials against identity.nexar.com; queries go to the
GraphQL endpoint at api.nexar.com. Tokens are valid for up to 24h and are cached
in-process, because Nexar explicitly asks callers not to mint one per query.

Credentials are read, in order, from:
  1. whatever the UI passed in (pasted into the sidebar)
  2. NEXAR_CLIENT_ID / NEXAR_CLIENT_SECRET environment variables
  3. .streamlit/secrets.toml

Nothing here is hardcoded and nothing is logged.
"""

import os
import threading
import time

import requests

TOKEN_URL = "https://identity.nexar.com/connect/token"
GRAPHQL_URL = "https://api.nexar.com/graphql"
SCOPE = "supply.domain"

DEFAULT_TIMEOUT = 25


class NexarError(RuntimeError):
    """Any failure talking to Nexar - auth, transport or GraphQL-level."""


# --------------------------------------------------------------------------
# GraphQL
# --------------------------------------------------------------------------
# The field set every query shares, so match and search return identical shapes
# and the downstream pipeline never has to care which one produced a part.
PART_FIELDS = """
  mpn
  name
  shortDescription
  octopartUrl
  totalAvail
  manufacturer { name }
  category { name }
  bestDatasheet { url }
  medianPrice1000 { price currency convertedPrice convertedCurrency }
  specs { attribute { name shortname } displayValue }
  similarParts {
    mpn
    name
    manufacturer { name }
    totalAvail
  }
  sellers(includeBrokers: false) {
    company { name }
    offers {
      inventoryLevel
      factoryLeadDays
      moq
      packaging
      clickUrl
      prices { quantity price currency convertedPrice convertedCurrency }
    }
  }
"""

# One round trip resolves every MPN in the email. supMultiMatch takes a list of
# {mpn, limit} queries, so candidate validation, pricing, stock, lead time and
# the alternates list all arrive together.
MULTI_MATCH_QUERY = """
query ExpediteParts($queries: [SupPartMatchQuery!]!) {
  supMultiMatch(queries: $queries) {
    reference
    parts {
%s
    }
  }
}
""" % PART_FIELDS

# supSearchMpn does partial / fuzzy matching, so it handles a pasted product
# name or a half-remembered part number where supMultiMatch would miss.
SEARCH_QUERY = """
query SearchParts($q: String!, $limit: Int!) {
  supSearchMpn(q: $q, limit: $limit) {
    hits
    results {
      part {
%s
      }
    }
  }
}
""" % PART_FIELDS


class NexarClient:
    """Thin, cached client for the Nexar supply API."""

    def __init__(self, client_id, client_secret, timeout=DEFAULT_TIMEOUT):
        if not client_id or not client_secret:
            raise NexarError("Nexar client_id and client_secret are both required.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token = None
        self._expires_at = 0.0
        self._lock = threading.Lock()
        # Nexar's evaluation tier bills a LIFETIME part quota - every part a query
        # returns is deducted permanently. Rehearsing a demo would burn through it,
        # so resolved parts are cached and never fetched twice in a session.
        self._part_cache = {}
        self.parts_billed = 0
        self.cache_hits = 0

    # -- auth ---------------------------------------------------------------
    def _token_value(self):
        with self._lock:
            # refresh a minute early so a long query never races the expiry
            if self._token and time.time() < self._expires_at - 60:
                return self._token
            try:
                resp = requests.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": SCOPE,
                    },
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                raise NexarError("Could not reach Nexar identity service: {}".format(exc)) from exc

            if resp.status_code != 200:
                detail = resp.text[:200] if resp.text else "no detail"
                if resp.status_code in (400, 401):
                    raise NexarError(
                        "Nexar rejected those credentials ({}). Check the Client ID and "
                        "Secret, and that the application has the Supply scope. [{}]".format(
                            resp.status_code, detail)
                    )
                raise NexarError("Nexar token request failed ({}): {}".format(resp.status_code, detail))

            payload = resp.json()
            self._token = payload.get("access_token")
            if not self._token:
                raise NexarError("Nexar returned no access_token.")
            self._expires_at = time.time() + float(payload.get("expires_in", 3600))
            return self._token

    def check_connection(self):
        """Mint a token so the UI can show a real connected/not-connected state."""
        self._token_value()
        return True

    # -- queries ------------------------------------------------------------
    def _graphql(self, query, variables):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": "Bearer {}".format(self._token_value()),
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise NexarError("Could not reach the Nexar API: {}".format(exc)) from exc

        if resp.status_code == 429:
            raise NexarError("Nexar rate limit hit. Wait a moment and try again.")
        if resp.status_code != 200:
            raise NexarError("Nexar API returned {}: {}".format(resp.status_code, resp.text[:200]))

        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in payload["errors"])
            if "part limit" in messages.lower() or "upgrade your plan" in messages.lower():
                raise NexarError(
                    "This Nexar application has no parts quota. Applications you create "
                    "yourself start at a limit of 0 - the free parts live on the "
                    "pre-created \"Evaluation\" app. Either use that app's Client ID and "
                    "Secret, or open \"Manage supply plan\" on this app to assign your "
                    "evaluation parts. (Nexar said: {})".format(messages)
                )
            raise NexarError("Nexar GraphQL error: {}".format(messages))
        data = payload.get("data")
        if data is None:
            raise NexarError("Nexar returned an empty response.")
        return data

    def match_mpns(self, mpns, limit=1, use_cache=True):
        """
        Resolve a list of MPN strings in a single request.

        Returns {submitted_mpn: part_dict}. MPNs Nexar does not recognise are
        simply absent - which is what filters junk out of the email parser.

        Anything already resolved this session is served from cache, so running
        the same demo repeatedly costs nothing against the part quota. Known
        misses are cached too, so junk tokens are only ever billed once.
        """
        mpns = [m for m in dict.fromkeys(mpns) if m]
        if not mpns:
            return {}

        resolved, to_fetch = {}, []
        for mpn in mpns:
            key = mpn.upper()
            if use_cache and key in self._part_cache:
                self.cache_hits += 1
                cached = self._part_cache[key]
                if cached is not None:
                    resolved[mpn] = cached
            else:
                to_fetch.append(mpn)

        if not to_fetch:
            return resolved

        variables = {"queries": [{"mpn": m, "limit": limit, "reference": m} for m in to_fetch]}
        data = self._graphql(MULTI_MATCH_QUERY, variables)

        hits = {}
        for result in data.get("supMultiMatch") or []:
            parts = result.get("parts") or []
            if not parts:
                continue
            reference = result.get("reference") or parts[0].get("mpn")
            hits[reference] = parts[0]

        for mpn in to_fetch:
            part = hits.get(mpn)
            self._part_cache[mpn.upper()] = part      # None records a known miss
            if part is not None:
                resolved[mpn] = part
                self.parts_billed += 1

        return resolved

    def search_parts(self, query, limit=5, use_cache=True):
        """
        Free-text search: a full MPN, a partial one, or a product description.

        Returns a list of part dicts in the same shape match_mpns produces.
        Results are cached per (query, limit) so re-running a search during a
        demo costs nothing against the part quota.
        """
        query = (query or "").strip()
        if not query:
            return []

        cache_key = ("search", query.lower(), limit)
        if use_cache and cache_key in self._part_cache:
            self.cache_hits += 1
            return self._part_cache[cache_key] or []

        data = self._graphql(SEARCH_QUERY, {"q": query, "limit": limit})
        payload = data.get("supSearchMpn") or {}
        parts = [
            row.get("part") for row in (payload.get("results") or [])
            if row.get("part")
        ]

        self._part_cache[cache_key] = parts
        self.parts_billed += len(parts)
        # Seed the per-MPN cache too, so a later exact lookup is already paid for.
        for part in parts:
            mpn = (part.get("mpn") or "").upper()
            if mpn and mpn not in self._part_cache:
                self._part_cache[mpn] = part
        return parts

    @property
    def cached_parts(self):
        return sum(1 for v in self._part_cache.values()
                   if v is not None and not isinstance(v, list))


# --------------------------------------------------------------------------
# Credential discovery
# --------------------------------------------------------------------------
def resolve_credentials(explicit_id=None, explicit_secret=None):
    """Find Nexar credentials from the UI, the environment, or Streamlit secrets."""
    if explicit_id and explicit_secret:
        return explicit_id.strip(), explicit_secret.strip(), "pasted into the sidebar"

    env_id = os.environ.get("NEXAR_CLIENT_ID")
    env_secret = os.environ.get("NEXAR_CLIENT_SECRET")
    if env_id and env_secret:
        return env_id.strip(), env_secret.strip(), "environment variables"

    try:
        import streamlit as st

        secrets = st.secrets
        if "NEXAR_CLIENT_ID" in secrets and "NEXAR_CLIENT_SECRET" in secrets:
            return (
                str(secrets["NEXAR_CLIENT_ID"]).strip(),
                str(secrets["NEXAR_CLIENT_SECRET"]).strip(),
                ".streamlit/secrets.toml",
            )
    except Exception:
        # No secrets file, or Streamlit not running - fall through to "none found"
        pass

    return None, None, None
