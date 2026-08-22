"""Connection management for DocuSign Connector: connect/disconnect/list,
consent URL, storing JWT Grant connections as a JSON array under one
secret, same shape as CircleCI Connector's / Redox Connector's handlers.
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from schemas import (
    NoParams,
    ConnectDocusignParams, ProviderConnection, ProviderConnectionList,
    DisconnectDocusignParams, DeleteResult,
    GetConsentUrlParams, ConsentUrlResult,
)

_SECRET_NAME = "docusign_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        return None
    return connections[0]


def _connection_to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        title=c.get("label") or c.get("account_name") or "DocuSign account",
        connected=True,
        detail=f"{c.get('environment', 'demo')} · account {c.get('account_id', '') or '—'}",
        environment=c.get("environment", "demo"),
        account_id=c.get("account_id", ""),
        consent_required=bool(c.get("consent_required", False)),
    )


async def resolve_or_error(ctx, connection_id: str = ""):
    """Resolve a connection or return the standard 'not connected'
    ActionResult.error. Returns (conn, error_or_None). The DocuSign client
    signs+exchanges its own token per call (see docusign_client.py), so
    callers pass the connection dict itself through, not a token."""
    conn = await resolve_connection(ctx, connection_id)
    if not conn:
        return None, ActionResult.error(
            "No DocuSign connection found. Connect one with connect_docusign first.",
            code="DOCUSIGN_NOT_CONNECTED",
        )
    return conn, None


@chat.function(
    "connect_docusign",
    "Connect your own DocuSign account via JWT Grant (service integration) by saving your Integration Key, "
    "impersonated User ID, and RSA private key, after checking they actually work end-to-end (sign a JWT, "
    "exchange for a token, and resolve your account via /oauth/userinfo). If DocuSign reports consent_required, "
    "the connection is still saved but flagged -- call get_consent_url next, open it in a browser, log in as that "
    "user, and approve once; then this connection starts working automatically on the next call.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="docusign-connector.connect",
    effects=["docusign.connection.created"],
)
async def connect_docusign(ctx, params: ConnectDocusignParams) -> ActionResult:
    """Connect your own DocuSign account via JWT Grant (service integration) by saving your Integration Key, impersonated User ID, and RSA private key, after checking they actually work end-to-end (sign a JWT, exchange for a token, and resolve your account via /oauth/userinfo)."""
    if not params.integration_key.strip() or not params.user_id.strip() or not params.private_key_pem.strip():
        return ActionResult.error(
            "Integration Key, User ID, and private key are all required.",
            code="DOCUSIGN_MISSING_FIELDS",
        )
    environment = params.environment if params.environment in ("demo", "production") else "demo"
    conn = {
        "id": str(uuid.uuid4()),
        "label": params.label.strip(),
        "environment": environment,
        "client_id": params.integration_key.strip(),
        "user_id": params.user_id.strip(),
        "private_key_pem": params.private_key_pem,
        "account_id": "",
        "base_uri": "",
        "account_name": "",
        "consent_required": False,
    }
    check = await dc.check_connection(ctx, conn)
    if not check.get("ok"):
        if check.get("error_code") == dc.CONSENT_REQUIRED:
            conn["consent_required"] = True
        else:
            return ActionResult.error(check.get("error", "Could not connect to DocuSign."), code=check.get("error_code", "DOCUSIGN_ERROR"))
    else:
        conn["account_id"] = check.get("account_id", "")
        conn["base_uri"] = check.get("base_uri", "")
        conn["account_name"] = check.get("account_name", "")

    connections = await _load_connections(ctx)
    connections.append(conn)
    await _save_connections(ctx, connections)
    return ActionResult.ok(_connection_to_entity(conn))


@chat.function(
    "disconnect_docusign",
    "Disconnect a DocuSign account: deletes the saved Integration Key/User ID/private key. Nothing in DocuSign "
    "itself is changed; envelopes/templates already sent are untouched.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.disconnect",
    effects=["docusign.connection.deleted"],
)
async def disconnect_docusign(ctx, params: DisconnectDocusignParams) -> ActionResult:
    """Disconnect a DocuSign account: deletes the saved Integration Key/User ID/private key."""
    connections = await _load_connections(ctx)
    target = params.connection_id or (connections[0]["id"] if connections else "")
    remaining = [c for c in connections if c.get("id") != target]
    if len(remaining) == len(connections):
        return ActionResult.error("No such DocuSign connection.", code="DOCUSIGN_NOT_CONNECTED")
    await _save_connections(ctx, remaining)
    return ActionResult.ok(DeleteResult(id=target, deleted=True))


@chat.function(
    "list_connections",
    "List the connected DocuSign accounts and whether each still needs one-time admin consent.",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
    event="docusign-connector.list_connections",
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List the connected DocuSign accounts and whether each still needs one-time admin consent."""
    connections = await _load_connections(ctx)
    return ActionResult.ok(ProviderConnectionList(items=[_connection_to_entity(c) for c in connections]))


@chat.function(
    "get_consent_url",
    "Build the one-time browser consent URL a DocuSign user must open and approve before JWT Grant will work for "
    "them. Needed only once per Integration Key + User ID pair, or again if consent was ever revoked.",
    action_type="read",
    chain_callable=True,
    data_model=ConsentUrlResult,
    event="docusign-connector.get_consent_url",
)
async def get_consent_url(ctx, params: GetConsentUrlParams) -> ActionResult:
    """Build the one-time browser consent URL a DocuSign user must open and approve before JWT Grant will work for them."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    url = dc.build_consent_url(conn["client_id"], conn.get("environment", "demo"))
    return ActionResult.ok(ConsentUrlResult(consent_url=url, environment=conn.get("environment", "demo")))
