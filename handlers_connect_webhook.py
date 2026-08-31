"""Docusign Connect (webhooks) chat functions for DocuSign Connector:
create/update/delete Connect configurations, list configs, and inspect/
retry delivery failures. Built on docusign_client.py / schemas.py.

WHY THIS MATTERS MOST OF ANY SECTION: DocuSign's own docs recommend
Connect over polling for any application that wants near-real-time
envelope/recipient status -- this is the section that lets Imperal chain
workflows off "envelope completed"/"recipient declined" without a poll
loop, same role Slack/Discord's outgoing webhooks or CircleCI's own
webhooks play in this portfolio.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ConnectConfig, ConnectConfigList, CreateConnectWebhookParams,
    UpdateConnectWebhookParams, DeleteConnectWebhookParams,
    ConnectLog, ConnectLogList, GetConnectFailuresParams,
    RetryConnectFailureParams, ConnScopedParams, DeleteResult,
)


def _connect_from_api(c: dict) -> ConnectConfig:
    return ConnectConfig(
        id=c.get("connectId", ""), name=c.get("name", ""),
        url_to_publish_to=c.get("urlToPublishTo", ""),
        enabled=c.get("enableLog", "") or c.get("allowEnvelopePublish", ""),
        events_json=json.dumps(c.get("envelopeEvents", [])),
    )


@chat.function(
    "create_connect_webhook",
    "Create a Docusign Connect webhook configuration: DocuSign will POST envelope/recipient status changes "
    "(sent, delivered, completed, declined, voided, etc) to your HTTPS endpoint in near-real-time instead of you "
    "polling for status.",
    action_type="write",
    chain_callable=True,
    data_model=ConnectConfig,
    event="docusign-connector.create_connect_webhook",
    effects=["docusign.connect.created"],
)
async def create_connect_webhook(ctx, params: CreateConnectWebhookParams) -> ActionResult:
    """Create a Docusign Connect webhook configuration: DocuSign will POST envelope/recipient status changes (sent, delivered, completed, declined, voided, etc) to your HTTPS endpoint in near-real-time instead of you polling for status."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        events = json.loads(params.events_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("events_json must be a valid JSON array.", code="DOCUSIGN_INVALID_JSON")
    body = {
        "name": params.name,
        "urlToPublishTo": params.url_to_publish_to,
        "envelopeEvents": events or ["Sent", "Delivered", "Completed", "Declined", "Voided"],
        "includeDocuments": "true" if params.include_documents else "false",
        "allowEnvelopePublish": "true",
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/connect", json_body=body, action="create_connect_webhook")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(ConnectConfig(
        id=data.get("connectId", ""), name=params.name, url_to_publish_to=params.url_to_publish_to,
        enabled="true", events_json=params.events_json,
    ), summary="Connect webhook created.")


@chat.function(
    "list_connect_webhooks",
    "List Docusign Connect webhook configurations set up in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=ConnectConfigList,
    event="docusign-connector.list_connect_webhooks",
)
async def list_connect_webhooks(ctx, params: ConnScopedParams) -> ActionResult:
    """List Docusign Connect webhook configurations set up in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/connect", action="list_connect_webhooks")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("configurations", []) if isinstance(data, dict) else []
    return ActionResult.success(ConnectConfigList(items=[_connect_from_api(c) for c in items]), summary="Connect webhooks listed.")


@chat.function(
    "update_connect_webhook",
    "Update a Docusign Connect webhook configuration's name, URL, or enabled state.",
    action_type="write",
    chain_callable=True,
    data_model=ConnectConfig,
    event="docusign-connector.update_connect_webhook",
    effects=["docusign.connect.updated"],
)
async def update_connect_webhook(ctx, params: UpdateConnectWebhookParams) -> ActionResult:
    """Update a Docusign Connect webhook configuration's name, URL, or enabled state."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body: dict = {"connectId": params.connect_id}
    if params.name:
        body["name"] = params.name
    if params.url_to_publish_to:
        body["urlToPublishTo"] = params.url_to_publish_to
    if params.enabled:
        body["allowEnvelopePublish"] = params.enabled
    try:
        await dc.request(ctx, conn, "PUT", "/connect", json_body=body, action="update_connect_webhook")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(ConnectConfig(id=params.connect_id, name=params.name, url_to_publish_to=params.url_to_publish_to, enabled=params.enabled), summary="Connect webhook updated.")


@chat.function(
    "delete_connect_webhook",
    "Delete a Docusign Connect webhook configuration.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.delete_connect_webhook",
    effects=["docusign.connect.deleted"],
)
async def delete_connect_webhook(ctx, params: DeleteConnectWebhookParams) -> ActionResult:
    """Delete a Docusign Connect webhook configuration."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await dc.request(ctx, conn, "DELETE", f"/connect/{params.connect_id}", action="delete_connect_webhook")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(DeleteResult(id=params.connect_id, deleted=True), summary="Connect webhook deleted.")


@chat.function(
    "get_connect_failures",
    "List Docusign Connect delivery failures (webhook deliveries that failed) for this account, so you can diagnose "
    "or retry them.",
    action_type="read",
    chain_callable=True,
    data_model=ConnectLogList,
    event="docusign-connector.get_connect_failures",
)
async def get_connect_failures(ctx, params: GetConnectFailuresParams) -> ActionResult:
    """List Docusign Connect delivery failures (webhook deliveries that failed) for this account, so you can diagnose or retry them."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/connect/failures", action="get_connect_failures")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("failures", []) if isinstance(data, dict) else []
    return ActionResult.success(ConnectLogList(items=[
        ConnectLog(
            connect_id=fa.get("connectDebugLog", {}).get("connectId", "") if isinstance(fa.get("connectDebugLog"), dict) else "",
            status=fa.get("failureType", ""), logged_at=fa.get("timestamp", ""), envelope_id=fa.get("envelopeId", ""),
        )
        for fa in items
    ]), summary="Connect failures retrieved.")


@chat.function(
    "retry_connect_failure",
    "Retry a single failed Docusign Connect webhook delivery.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.retry_connect_failure",
    effects=["docusign.connect.retried"],
)
async def retry_connect_failure(ctx, params: RetryConnectFailureParams) -> ActionResult:
    """Retry a single failed Docusign Connect webhook delivery."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await dc.request(ctx, conn, "PUT", f"/connect/failures/{params.failure_id}", action="retry_connect_failure")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(DeleteResult(id=params.failure_id, deleted=False), summary="Retry connect failure done.")
