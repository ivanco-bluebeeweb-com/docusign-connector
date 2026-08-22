"""DocuSign HTTP client -- JWT Grant auth + eSignature REST API v2.1.
Function-based, `ctx.http`-driven, same shape as Redox Connector's
redox_client.py / CircleCI Connector's circleci_client.py (no raw
httpx.AsyncClient -- SDK's own context-bound HTTP client only). See
app.py's module docstring for the full architectural reasoning behind
BYOK + JWT Grant.

AUTH (confirmed via developers.docusign.com/platform/auth/jwt/,
2026-08-22):

JWT Grant -- `POST {auth_server}/oauth/token` with
`grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer` +
`assertion=<signed JWT>`. The JWT is signed RS256 with the user's own RSA
private key, claims: iss=Integration Key (client_id), sub=impersonated
User ID, aud=auth server host, scope="signature impersonation", iat/exp
(max 1h). `auth_server` is `account-d.docusign.com` (demo) or
`account.docusign.com` (production) -- a real domain difference, not a
query flag.

Right after a successful token exchange, `GET {auth_server}/oauth/userinfo`
resolves `sub` (DocuSign user id), `accounts[].account_id`, and
`accounts[].base_uri` (the account's actual data-center host, e.g.
`https://na3.docusign.net`) -- these are cached on the connection record
and reused, never asked of the user.

REST base once resolved: `{base_uri}/restapi/v2.1/accounts/{account_id}`.

Tokens are NOT cached across chat-function calls (each call gets a fresh
ctx/connection dict from secrets, and persisting a short-lived token back
into the stored connection record would need an extra secrets.set on every
single call to save ~55 minutes of reuse) -- every call re-signs a JWT and
re-authenticates once, then reuses that token for any follow-up requests
within the SAME call (e.g. bulk loops), matching the Redox/MuleSoft/Power
Automate/n8n precedent of "token per call, not persisted."
"""
from __future__ import annotations

import time
import uuid
from typing import Any

DEMO_AUTH_HOST = "account-d.docusign.com"
PROD_AUTH_HOST = "account.docusign.com"

UNAUTHORIZED = "DOCUSIGN_UNAUTHORIZED"
CONSENT_REQUIRED = "DOCUSIGN_CONSENT_REQUIRED"
FORBIDDEN = "DOCUSIGN_FORBIDDEN"
NOT_FOUND = "DOCUSIGN_NOT_FOUND"
VALIDATION_FAILED = "DOCUSIGN_VALIDATION_FAILED"
RESPONSE_UNEXPECTED = "DOCUSIGN_RESPONSE_UNEXPECTED"
RATE_LIMITED = "DOCUSIGN_RATE_LIMITED"
BACKEND_5XX = "DOCUSIGN_BACKEND_5XX"
MISSING_DEPENDENCY = "DOCUSIGN_MISSING_DEPENDENCY"
JWT_SIGN_FAILED = "DOCUSIGN_JWT_SIGN_FAILED"
USERINFO_FAILED = "DOCUSIGN_USERINFO_FAILED"

_MESSAGES = {
    UNAUTHORIZED: "DocuSign rejected these credentials. Check the Integration Key/User ID/private key, then reconnect.",
    CONSENT_REQUIRED: "This DocuSign user has not granted consent to the Integration Key yet. Open the consent URL from connect_docusign once in a browser, log in, and approve, then try again.",
    FORBIDDEN: "DocuSign accepted the token but denied this operation -- the impersonated user's permission profile likely lacks the required permission.",
    NOT_FOUND: "DocuSign has no such resource, or this account cannot access it.",
    VALIDATION_FAILED: "DocuSign rejected the request as invalid.",
    RESPONSE_UNEXPECTED: "DocuSign returned a response the connector could not safely interpret.",
    RATE_LIMITED: "DocuSign is rate-limiting requests (burst or hourly API limit); try again shortly.",
    BACKEND_5XX: "DocuSign returned a server error; try again shortly.",
    MISSING_DEPENDENCY: "The pyjwt library required for JWT Grant auth is not installed.",
    JWT_SIGN_FAILED: "Failed to sign the JWT assertion with the stored RSA private key.",
    USERINFO_FAILED: "Could not resolve this DocuSign account's base_uri/account_id via /oauth/userinfo.",
}
_RETRYABLE = {RATE_LIMITED, BACKEND_5XX}


def fail(code: str, detail: str = "") -> dict:
    message = _MESSAGES.get(code, code)
    if detail:
        message = f"{message} ({detail})"
    return {"ok": False, "error_code": code, "error": message, "retryable": code in _RETRYABLE}


class ClientFail(Exception):
    def __init__(self, payload: dict):
        super().__init__(payload.get("error", "DocuSign request failed"))
        self.payload = payload
        self.message = payload.get("error", "DocuSign request failed")


def auth_host(environment: str) -> str:
    return PROD_AUTH_HOST if environment == "production" else DEMO_AUTH_HOST


def build_consent_url(client_id: str, environment: str, redirect_uri: str = "https://www.docusign.com") -> str:
    """One-time browser consent URL the impersonated user must visit and
    approve before JWT Grant will work for them -- DocuSign returns
    consent_required otherwise. Built, not asked of the user, per
    developers.docusign.com/platform/auth/jwt-get-token/."""
    host = auth_host(environment)
    return (
        f"https://{host}/oauth/auth?response_type=code&scope=signature%20impersonation"
        f"&client_id={client_id}&redirect_uri={redirect_uri}"
    )


def _build_jwt_assertion(client_id: str, user_id: str, private_key_pem: str, environment: str) -> dict:
    """Returns {"ok": True, "assertion": ...} or a fail() dict. Pure local
    signing -- no network call, so it doesn't need ctx.http."""
    try:
        import jwt as pyjwt  # PyJWT
    except ImportError:
        return fail(MISSING_DEPENDENCY)

    host = auth_host(environment)
    now = int(time.time())
    claims = {
        "iss": client_id,
        "sub": user_id,
        "aud": host,
        "iat": now,
        "exp": now + 3600,
        "scope": "signature impersonation",
        "jti": str(uuid.uuid4()),
    }
    try:
        assertion = pyjwt.encode(claims, private_key_pem, algorithm="RS256")
        return {"ok": True, "assertion": assertion}
    except Exception as exc:
        return fail(JWT_SIGN_FAILED, str(exc))


async def get_access_token(ctx, conn: dict) -> dict:
    """Exchange a freshly signed JWT assertion for an access token.
    Returns {"ok": True, "access_token": ..., "expires_in": ...} or a
    fail() dict. Callers are responsible for TTL caching."""
    built = _build_jwt_assertion(
        conn.get("client_id", ""), conn.get("user_id", ""),
        conn.get("private_key_pem", ""), conn.get("environment", "demo"),
    )
    if not built.get("ok"):
        return built
    host = auth_host(conn.get("environment", "demo"))
    resp = await ctx.http.post(
        f"https://{host}/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": built["assertion"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    body = resp.body if isinstance(resp.body, dict) else {}
    if resp.status_code == 400 and body.get("error") == "consent_required":
        return fail(CONSENT_REQUIRED)
    if resp.status_code in (400, 401):
        return fail(UNAUTHORIZED, body.get("error_description") or body.get("error", ""))
    if resp.status_code >= 500:
        return fail(BACKEND_5XX)
    if resp.status_code != 200:
        return fail(RESPONSE_UNEXPECTED, f"token endpoint returned {resp.status_code}")
    token = body.get("access_token")
    if not token:
        return fail(RESPONSE_UNEXPECTED, "token response had no access_token")
    return {"ok": True, "access_token": token, "expires_in": body.get("expires_in", 3600)}


async def resolve_userinfo(ctx, conn: dict, access_token: str) -> dict:
    """GET /oauth/userinfo -- resolves account_id + base_uri for the
    impersonated user's default (or matching) account. Returns
    {"ok": True, "account_id": ..., "base_uri": ...} or a fail() dict."""
    host = auth_host(conn.get("environment", "demo"))
    resp = await ctx.http.get(
        f"https://{host}/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status_code != 200:
        return fail(USERINFO_FAILED, f"HTTP {resp.status_code}")
    body = resp.body if isinstance(resp.body, dict) else {}
    accounts = body.get("accounts") or []
    if not accounts:
        return fail(USERINFO_FAILED, "no accounts returned for this user")
    account_id_pref = conn.get("account_id", "")
    account = next((a for a in accounts if a.get("account_id") == account_id_pref), None) or \
        next((a for a in accounts if a.get("is_default")), None) or accounts[0]
    return {
        "ok": True,
        "account_id": account.get("account_id", ""),
        "base_uri": account.get("base_uri", ""),
        "account_name": account.get("account_name", ""),
    }


async def check_connection(ctx, conn: dict) -> dict:
    """Full end-to-end verification: sign+exchange a token, then resolve
    userinfo -- proves the RSA key/consent/impersonation chain actually
    works, not just that the JWT was well-formed."""
    tok = await get_access_token(ctx, conn)
    if not tok.get("ok"):
        return tok
    info = await resolve_userinfo(ctx, conn, tok["access_token"])
    if not info.get("ok"):
        return info
    return {"ok": True, **info, "access_token": tok["access_token"], "expires_in": tok["expires_in"]}


async def ensure_token(ctx, conn: dict) -> dict:
    """Sign a fresh JWT and exchange it for an access token for this call.
    Returns {"ok": True, "access_token": ...} or fail(). See module
    docstring for why tokens are not cached across calls."""
    return await get_access_token(ctx, conn)


def _headers(access_token: str, extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


def _check_status(resp, action: str) -> Any:
    if resp.status_code in (200, 201, 202):
        return resp.body if isinstance(resp.body, (dict, list)) else {}
    if resp.status_code == 204:
        return {}
    body = resp.body if isinstance(resp.body, dict) else {}
    detail = body.get("message") or body.get("errorCode") or ""
    if resp.status_code == 401:
        raise ClientFail(fail(UNAUTHORIZED, f"{action}: {detail}" if detail else action))
    if resp.status_code == 403:
        raise ClientFail(fail(FORBIDDEN, f"{action}: {detail}" if detail else action))
    if resp.status_code == 404:
        raise ClientFail(fail(NOT_FOUND, f"{action}: {detail}" if detail else action))
    if resp.status_code == 429:
        raise ClientFail(fail(RATE_LIMITED, action))
    if resp.status_code >= 500:
        raise ClientFail(fail(BACKEND_5XX, action))
    if resp.status_code == 400:
        raise ClientFail(fail(VALIDATION_FAILED, f"{action}: {detail}" if detail else action))
    raise ClientFail(fail(RESPONSE_UNEXPECTED, f"{action}: HTTP {resp.status_code} {detail}"))


def rest_base(conn: dict) -> str:
    base_uri = conn.get("base_uri", "")
    account_id = conn.get("account_id", "")
    return f"{base_uri}/restapi/v2.1/accounts/{account_id}"


async def request(
    ctx, conn: dict, method: str, path: str, *,
    json_body: dict | None = None, params: dict | None = None, action: str = "",
) -> Any:
    """Generic authenticated REST call against the eSignature API. `path`
    is relative to the account root, e.g. '/envelopes'."""
    tok = await ensure_token(ctx, conn)
    if not tok.get("ok"):
        raise ClientFail(tok)
    url = f"{rest_base(conn)}{path}"
    headers = _headers(tok["access_token"], {"Content-Type": "application/json"})
    if method == "GET":
        resp = await ctx.http.get(url, headers=headers, params=params)
    elif method == "POST":
        resp = await ctx.http.post(url, headers=headers, json=json_body or {})
    elif method == "PUT":
        resp = await ctx.http.put(url, headers=headers, json=json_body or {})
    elif method == "DELETE":
        resp = await ctx.http.delete(url, headers=headers, json=json_body) if json_body else await ctx.http.delete(url, headers=headers)
    else:
        raise ClientFail(fail(RESPONSE_UNEXPECTED, f"unsupported method {method}"))
    return _check_status(resp, action or f"{method} {path}")
