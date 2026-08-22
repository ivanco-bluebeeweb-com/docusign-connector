"""Bulk send chat functions for DocuSign Connector: bulk recipient lists,
sending one template/envelope to a whole list in one batch, and checking
batch status. Built on docusign_client.py / schemas.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    CreateBulkSendListParams, BulkList, BulkListList,
    SendBulkEnvelopeParams, BulkSendResult,
    GetBulkSendBatchStatusParams, BulkSendBatchStatus,
    ConnScopedParams,
)


@chat.function(
    "create_bulk_send_list",
    "Create a DocuSign bulk send recipient list -- a named set of people who will each get their own copy of an "
    "envelope in one batch operation (e.g. sending the same NDA to 50 new vendors at once).",
    action_type="write",
    chain_callable=True,
    data_model=BulkList,
    event="docusign-connector.create_bulk_send_list",
    effects=["docusign.bulk_list.created"],
)
async def create_bulk_send_list(ctx, params: CreateBulkSendListParams) -> ActionResult:
    """Create a DocuSign bulk send recipient list -- a named set of people who will each get their own copy of an envelope in one batch operation (e.g."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        rows = json.loads(params.recipients_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("recipients_json must be a valid JSON array.", code="DOCUSIGN_INVALID_JSON")
    if not isinstance(rows, list) or not rows:
        return ActionResult.error("At least one recipient row is required.", code="DOCUSIGN_MISSING_RECIPIENTS")
    body = {
        "name": params.name,
        "bulkCopies": [
            {
                "recipients": [{
                    "name": r.get("name", ""), "email": r.get("email", ""),
                    "roleName": r.get("role_name", ""),
                }],
            }
            for r in rows
        ],
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/bulk_send_lists", json_body=body, action="create_bulk_send_list")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(BulkList(
        id=data.get("listId", ""), name=params.name, recipient_count=str(len(rows)),
    ))


@chat.function(
    "list_bulk_send_lists",
    "List saved bulk send recipient lists in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=BulkListList,
    event="docusign-connector.list_bulk_send_lists",
)
async def list_bulk_send_lists(ctx, params: ConnScopedParams) -> ActionResult:
    """List saved bulk send recipient lists in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/bulk_send_lists", action="list_bulk_send_lists")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    lists = data.get("bulkSendLists", []) if isinstance(data, dict) else []
    return ActionResult.ok(BulkListList(items=[
        BulkList(id=b.get("listId", ""), name=b.get("name", ""), recipient_count=str(len(b.get("bulkCopies", []))))
        for b in lists
    ]))


@chat.function(
    "send_bulk_envelope",
    "Send one envelope built from a template to every recipient in a bulk send list, in a single batch request.",
    action_type="write",
    chain_callable=True,
    data_model=BulkSendResult,
    event="docusign-connector.send_bulk_envelope",
    effects=["docusign.envelope.bulk_sent"],
)
async def send_bulk_envelope(ctx, params: SendBulkEnvelopeParams) -> ActionResult:
    """Send one envelope built from a template to every recipient in a bulk send list, in a single batch request."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    draft_body = {
        "envelopeIdOrTemplateId": params.template_id,
        "envelopeDefinition": {"templateId": params.template_id, "emailSubject": params.email_subject},
    }
    try:
        draft = await dc.request(
            ctx, conn, "POST", f"/bulk_send_lists/{params.bulk_list_id}/send",
            json_body=draft_body, action="send_bulk_envelope",
        )
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(BulkSendResult(
        batch_id=draft.get("batchId", ""), envelope_or_template_id=params.template_id,
    ))


@chat.function(
    "get_bulk_send_batch_status",
    "Check the status of a previously started bulk send batch (how many envelopes were sent vs failed).",
    action_type="read",
    chain_callable=True,
    data_model=BulkSendBatchStatus,
    event="docusign-connector.get_bulk_send_batch_status",
)
async def get_bulk_send_batch_status(ctx, params: GetBulkSendBatchStatusParams) -> ActionResult:
    """Check the status of a previously started bulk send batch (how many envelopes were sent vs failed)."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(
            ctx, conn, "GET", f"/bulk_send_batch/{params.batch_id}",
            action="get_bulk_send_batch_status",
        )
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(BulkSendBatchStatus(
        batch_id=params.batch_id,
        status=data.get("batchStatus", ""),
        envelopes_sent=str(data.get("envelopeCount", "") or data.get("sent", "") or ""),
        envelopes_failed=str(data.get("failed", "") or ""),
    ))
