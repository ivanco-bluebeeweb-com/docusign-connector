"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), same reasoning as Salesforce Connector /
MuleSoft Connector / CircleCI Connector / Redox Connector. A DocuSign
account lives inside the USER'S OWN DocuSign account -- Imperal cannot and
should not broker access to someone else's e-signature account centrally.

WHY JWT GRANT (service integration), NOT AUTHORIZATION CODE GRANT, AND NOT
built-in `ext.oauth`.

DocuSign is not among the platform's built-in ext.oauth providers (google/
microsoft/yahoo only). Of DocuSign's two real OAuth flows (confirmed
developers.docusign.com/platform/auth/, 2026-08-22), JWT Grant is chosen
over Authorization Code Grant for the same reason Salesforce Connector
chose Client Credentials Flow over delegated user OAuth: it is a service
integration (impersonates one specific DocuSign user on a long-term basis,
no browser redirect needed on every call) rather than a per-end-user
delegated login. The user pays for this with a one-time manual consent
grant (a URL the connector builds and hands back, same shape as GitLab
CI/CD's "here's where to get your token" guided path, just one extra
step: generate an RSA keypair in DocuSign Admin, register the public key,
grant consent once via the browser).

WHY THE RSA PRIVATE KEY IS STORED, NOT A READY-MADE TOKEN, SAME REASONING
AS REDOX CONNECTOR'S OAuth API key mode.

JWT Grant access tokens live at most 1 hour and are never handed a refresh
token -- the connector must re-sign a fresh JWT assertion with the user's
own RSA private key every time a token is needed. So the connection record
holds the durable material (Integration Key/client_id, impersonated User
ID, RSA private key PEM, environment) rather than a token; docusign_client
signs and exchanges for a token on demand, matching Redox Connector's
`_build_jwt_assertion` / `get_access_token` pattern.

WHY `account_id`/`base_uri` ARE RESOLVED DYNAMICALLY, NOT ASKED OF THE
USER.

DocuSign returns the account_id/base_uri pair for the impersonated user via
`GET /oauth/userinfo` right after the first successful token exchange --
`base_uri` depends on the account's assigned data center (e.g.
`na3.docusign.net`) and is not derivable from anything the user could type
in. The connector calls `/oauth/userinfo` once per connect (and again if a
stale value ever 401s), caches the result in the connection record, and
never asks the user to supply it manually -- unlike GitLab CI/CD, where a
self-hosted base URL genuinely cannot be inferred.

WHY TWO ENVIRONMENTS (demo/production), SAME SHAPE AS STRIPE/SHOPIFY
sandbox_mode.

DocuSign's sandbox (`account-d.docusign.com`) and production
(`account.docusign.com`) are physically separate systems with separate
accounts, not a query flag -- the user picks one at connect time (default
demo, for a safe first test), stored per connection.

WHY `write_mode="both"`, SAME REASONING AS EVERY OTHER BYOK CONNECTOR.

`connect_docusign` is the friendly guided path explaining the JWT consent
dance; the generic Secrets screen stays available as a fallback for
advanced users who already have credentials ready.

WHY SCOPE IS PER-ACCOUNT, NOT APP-LEVEL, SAME AS EVERY OTHER BYOK
CONNECTOR IN THIS PORTFOLIO.

A user may hold several distinct DocuSign accounts (e.g. personal +
client work) -- connections are stored as a JSON array under one secret
key, each entry with its own Integration Key/User ID/private key/
environment/cached token, identical shape to CircleCI Connector's
`circleci_connections` / Redox Connector's `redox_connections` list.

WHY DESTRUCTIVE ACTIONS ARE MARKED `action_type="destructive"`, SAME
PRINCIPLE AS EVERY OTHER CONNECTOR IN THIS PORTFOLIO.

Voiding an envelope, deleting a template/PowerForm/brand/Connect
configuration/custom tab, or deactivating a user cannot be undone through
this connector -- each such handler declares `action_type="destructive"`
so the platform's own confirmation card gates the call.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "docusign-connector",
    version="0.1.0",
    display_name="DocuSign",
    description=(
        "Connect your own DocuSign account (JWT Grant service integration) "
        "to send, track, and manage agreements end to end: create and send "
        "envelopes from documents or templates, manage recipients/tabs/"
        "voice authentication, void/resend/correct envelopes, build and "
        "manage templates, run bulk send to many recipients at once, "
        "manage PowerForms, folders, users/groups/permission profiles, "
        "account brands, Docusign Connect webhook configurations, custom "
        "tabs, and account diagnostics -- plus bulk operations and an "
        "account health audit. Uses your own DocuSign Integration Key -- "
        "nothing is hosted or proxied by Imperal beyond the request "
        "itself. Note: covers the eSignature REST API v2.1 domain only; "
        "Rooms, Click, Admin (org-level), Monitor, Maestro, Navigator, "
        "Web Forms, and legacy eNotary/Workspaces are separate DocuSign "
        "products and out of scope."
    ),
    icon="icon.svg",
    capabilities=[
        "docusign:read",
        "docusign:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="docusign",
    description=(
        "DocuSign Connector -- connect your own DocuSign account via JWT "
        "Grant (Integration Key + impersonated User ID + RSA private key), "
        "then create/send/track/void/resend envelopes, manage templates, "
        "bulk send, PowerForms, folders, users/groups/permission profiles, "
        "brands, Connect webhooks, custom tabs, account diagnostics, and "
        "run bulk operations and an account health audit."
    ),
)

ext.secret(
    "docusign_connections",
    (
        "Your connected DocuSign accounts -- stored as a JSON array, one "
        "entry per account, each with its Integration Key (client_id), "
        "impersonated User ID, RSA private key PEM, environment (demo/"
        "production), and a cached access token/account_id/base_uri. "
        "Managed through connect_docusign / disconnect_docusign -- you "
        "should not need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one connection is stored, same shape as CircleCI Connector's /
    Redox Connector's health_check."""
    import json as _json
    raw = await ctx.secrets.get("docusign_connections")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    return {
        "healthy": True,
        "detail": (
            f"{count} DocuSign account(s) connected." if count
            else "Not connected yet -- run connect_docusign."
        ),
    }
