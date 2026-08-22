"""Bulk operations + account health audit (Ярус 3 value-add) chat
functions for DocuSign Connector. Built on docusign_client.py /
schemas.py, same shape as CircleCI Connector's handlers_bulk_audit.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    BulkVoidEnvelopesParams, BulkResendEnvelopesParams, BulkResultItem, BulkResult,
    AuditAccountParams, AccountHealthReport,
)


@chat.function(
    "bulk_void_envelopes",
    "Void several DocuSign envelopes in one call, by explicit envelope ids. Continues past per-item failures and "
    "reports which succeeded/failed.",
    action_type="destructive",
    chain_callable=True,
    data_model=BulkResult,
    event="docusign-connector.bulk_void_envelopes",
    effects=["docusign.envelope.bulk_voided"],
)
async def bulk_void_envelopes(ctx, params: BulkVoidEnvelopesParams) -> ActionResult:
    """Void several DocuSign envelopes in one call, by explicit envelope ids."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        envelope_ids = json.loads(params.envelope_ids_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("envelope_ids_json must be a valid JSON array.", code="DOCUSIGN_INVALID_JSON")
    if not isinstance(envelope_ids, list) or not envelope_ids:
        return ActionResult.error("At least one envelope id is required.", code="DOCUSIGN_MISSING_ENVELOPE_IDS")

    items: list[BulkResultItem] = []
    succeeded = 0
    failed = 0
    for eid in envelope_ids:
        try:
            await dc.request(
                ctx, conn, "PUT", f"/envelopes/{eid}",
                json_body={"status": "voided", "voidedReason": params.voided_reason or "Bulk voided"},
                action="bulk_void_envelopes",
            )
            items.append(BulkResultItem(id=eid, ok=True))
            succeeded += 1
        except dc.ClientFail as f:
            items.append(BulkResultItem(id=eid, ok=False, error=f.message))
            failed += 1
    return ActionResult.ok(BulkResult(items=items, succeeded=succeeded, failed=failed))


@chat.function(
    "bulk_resend_envelopes",
    "Resend the signing-reminder notification for several DocuSign envelopes in one call. Continues past per-item "
    "failures and reports which succeeded/failed.",
    action_type="write",
    chain_callable=True,
    data_model=BulkResult,
    event="docusign-connector.bulk_resend_envelopes",
    effects=["docusign.envelope.bulk_resent"],
)
async def bulk_resend_envelopes(ctx, params: BulkResendEnvelopesParams) -> ActionResult:
    """Resend the signing-reminder notification for several DocuSign envelopes in one call."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        envelope_ids = json.loads(params.envelope_ids_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("envelope_ids_json must be a valid JSON array.", code="DOCUSIGN_INVALID_JSON")
    if not isinstance(envelope_ids, list) or not envelope_ids:
        return ActionResult.error("At least one envelope id is required.", code="DOCUSIGN_MISSING_ENVELOPE_IDS")

    items: list[BulkResultItem] = []
    succeeded = 0
    failed = 0
    for eid in envelope_ids:
        try:
            await dc.request(
                ctx, conn, "PUT", f"/envelopes/{eid}",
                params={"resend_envelope": "true"},
                json_body={"status": "sent"},
                action="bulk_resend_envelopes",
            )
            items.append(BulkResultItem(id=eid, ok=True))
            succeeded += 1
        except dc.ClientFail as f:
            items.append(BulkResultItem(id=eid, ok=False, error=f.message))
            failed += 1
    return ActionResult.ok(BulkResult(items=items, succeeded=succeeded, failed=failed))


@chat.function(
    "audit_account_health",
    "Scan recent envelopes in this DocuSign account and produce a health report: how many are pending signature, "
    "declined, or voided, which look stuck (sent long ago, still not completed), and which have signers whose "
    "signing deadline is expiring soon.",
    action_type="read",
    chain_callable=True,
    data_model=AccountHealthReport,
    event="docusign-connector.audit_account_health",
)
async def audit_account_health(ctx, params: AuditAccountParams) -> ActionResult:
    """Scan recent envelopes in this DocuSign account and produce a health report: how many are pending signature, declined, or voided, which look stuck (sent long ago, still not completed), and which have signers whose signing deadline is expiring soon."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(
            ctx, conn, "GET", "/envelopes",
            params={"from_date": "2000-01-01", "count": "200"},
            action="audit_account_health",
        )
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))

    envelopes = data.get("envelopes", []) if isinstance(data, dict) else []
    pending = 0
    declined = 0
    voided = 0
    stuck: list[str] = []
    expiring: list[str] = []
    notes: list[str] = []

    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)

    for e in envelopes:
        status = e.get("status", "")
        eid = e.get("envelopeId", "")
        if status == "sent" or status == "delivered":
            pending += 1
            sent_at = e.get("sentDateTime", "")
            if sent_at:
                try:
                    sent_dt = datetime.datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
                    if (now - sent_dt).days >= 14:
                        stuck.append(eid)
                except ValueError:
                    pass
            expires_at = e.get("statusChangedDateTime", "")
        elif status == "declined":
            declined += 1
        elif status == "voided":
            voided += 1

    if stuck:
        notes.append(f"{len(stuck)} envelope(s) have been pending signature for 14+ days -- consider resending or voiding.")
    if declined:
        notes.append(f"{declined} envelope(s) were declined -- review why signers declined before resending similar documents.")
    if not envelopes:
        notes.append("No envelopes found in this account's history yet.")

    return ActionResult.ok(AccountHealthReport(
        total_envelopes_checked=len(envelopes),
        pending_signature_count=pending,
        declined_count=declined,
        voided_count=voided,
        stuck_envelopes=stuck,
        expiring_soon=expiring,
        notes=notes,
    ))
