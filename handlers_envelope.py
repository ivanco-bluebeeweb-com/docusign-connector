"""Envelope lifecycle chat functions for DocuSign Connector: create/send
from a raw document or a template, list/get, void/resend/correct,
documents, recipients, tabs, audit events, and embedded signing URLs.
Built on docusign_client.py / schemas.py, same shape as CircleCI
Connector's / Redox Connector's handlers.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    Signer, Envelope, EnvelopeList,
    CreateEnvelopeParams, CreateEnvelopeFromTemplateParams,
    EnvelopeScopedParams, ListParams,
    VoidEnvelopeParams, ResendEnvelopeParams, CorrectEnvelopeParams,
    EnvelopeDocument, EnvelopeDocumentList, GetEnvelopeDocumentParams,
    DocumentContent, RecipientList, UpdateRecipientsParams,
    AddRecipientTabsParams, ListRecipientTabsParams, TabsResult,
    GetEnvelopeAuditEventsParams, AuditEvent, AuditEventList,
    GetSigningUrlParams, SigningUrlResult,
    DeleteResult,
)


def _signer_from_api(r: dict) -> Signer:
    return Signer(
        name=r.get("name", ""),
        email=r.get("email", ""),
        recipient_id=r.get("recipientId", ""),
        routing_order=r.get("routingOrder", ""),
        status=r.get("status", ""),
    )


def _envelope_from_api(e: dict) -> Envelope:
    return Envelope(
        id=e.get("envelopeId", ""),
        status=e.get("status", ""),
        email_subject=e.get("emailSubject", ""),
        email_blurb=e.get("emailBlurb", ""),
        sent_at=e.get("sentDateTime", ""),
        completed_at=e.get("completedDateTime", ""),
        created_at=e.get("createdDateTime", ""),
        signers=[],
    )


@chat.function(
    "create_envelope",
    "Create and send (or save as a draft) a DocuSign envelope from a raw document: uploads the document, attaches "
    "signers/CC recipients, and sends the signing request by email.",
    action_type="write",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.create_envelope",
    effects=["docusign.envelope.created"],
)
async def create_envelope(ctx, params: CreateEnvelopeParams) -> ActionResult:
    """Create and send (or save as a draft) a DocuSign envelope from a raw document: uploads the document, attaches signers/CC recipients, and sends the signing request by email."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.document_base64.strip() or not params.signers_json.strip():
        return ActionResult.error("A document and at least one signer are required.", code="DOCUSIGN_MISSING_FIELDS")
    try:
        signers_in = json.loads(params.signers_json)
        cc_in = json.loads(params.cc_json) if params.cc_json.strip() else []
    except (TypeError, ValueError):
        return ActionResult.error("signers_json/cc_json must be valid JSON.", code="DOCUSIGN_INVALID_JSON")

    signers = [
        {
            "name": s.get("name", ""), "email": s.get("email", ""),
            "recipientId": str(s.get("recipient_id") or i + 1),
            "routingOrder": str(s.get("routing_order") or "1"),
        }
        for i, s in enumerate(signers_in)
    ]
    carbon_copies = [
        {
            "name": c.get("name", ""), "email": c.get("email", ""),
            "recipientId": str(c.get("recipient_id") or f"cc{i + 1}"),
        }
        for i, c in enumerate(cc_in)
    ]
    body = {
        "emailSubject": params.email_subject,
        "emailBlurb": params.email_blurb,
        "documents": [{
            "documentBase64": params.document_base64,
            "name": params.document_name or "Document",
            "fileExtension": params.document_extension or "pdf",
            "documentId": "1",
        }],
        "recipients": {"signers": signers, "carbonCopies": carbon_copies},
        "status": params.status or "sent",
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/envelopes", json_body=body, action="create_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Envelope(
        id=data.get("envelopeId", ""), status=data.get("status", ""),
        email_subject=params.email_subject, email_blurb=params.email_blurb,
        signers=[Signer(name=s["name"], email=s["email"], recipient_id=s["recipientId"], routing_order=s["routingOrder"]) for s in signers],
    ))


@chat.function(
    "create_envelope_from_template",
    "Create and send (or save as a draft) a DocuSign envelope from an existing template, mapping template roles "
    "to real recipients.",
    action_type="write",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.create_envelope_from_template",
    effects=["docusign.envelope.created"],
)
async def create_envelope_from_template(ctx, params: CreateEnvelopeFromTemplateParams) -> ActionResult:
    """Create and send (or save as a draft) a DocuSign envelope from an existing template, mapping template roles to real recipients."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.template_id.strip() or not params.template_roles_json.strip():
        return ActionResult.error("A template id and at least one template role mapping are required.", code="DOCUSIGN_MISSING_FIELDS")
    try:
        roles_in = json.loads(params.template_roles_json)
    except (TypeError, ValueError):
        return ActionResult.error("template_roles_json must be valid JSON.", code="DOCUSIGN_INVALID_JSON")
    template_roles = [
        {"roleName": r.get("role_name", ""), "name": r.get("name", ""), "email": r.get("email", "")}
        for r in roles_in
    ]
    body = {
        "templateId": params.template_id,
        "emailSubject": params.email_subject,
        "templateRoles": template_roles,
        "status": params.status or "sent",
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/envelopes", json_body=body, action="create_envelope_from_template")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Envelope(id=data.get("envelopeId", ""), status=data.get("status", ""), email_subject=params.email_subject))


@chat.function(
    "list_envelopes",
    "List envelopes in this DocuSign account, optionally filtered by status and creation date.",
    action_type="read",
    chain_callable=True,
    data_model=EnvelopeList,
    event="docusign-connector.list_envelopes",
)
async def list_envelopes(ctx, params: ListParams) -> ActionResult:
    """List envelopes in this DocuSign account, optionally filtered by status and creation date."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"count": str(params.count)}
    if params.from_date.strip():
        query["from_date"] = params.from_date
    else:
        query["from_date"] = "2000-01-01"
    if params.status.strip():
        query["status"] = params.status
    try:
        data = await dc.request(ctx, conn, "GET", "/envelopes", params=query, action="list_envelopes")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    envelopes = data.get("envelopes", []) if isinstance(data, dict) else []
    return ActionResult.ok(EnvelopeList(
        items=[_envelope_from_api(e) for e in envelopes],
        total_set_size=str(data.get("totalSetSize", "")) if isinstance(data, dict) else "",
    ))


@chat.function(
    "get_envelope",
    "Get full status/details for one DocuSign envelope by id.",
    action_type="read",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.get_envelope",
)
async def get_envelope(ctx, params: EnvelopeScopedParams) -> ActionResult:
    """Get full status/details for one DocuSign envelope by id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/envelopes/{params.envelope_id}", action="get_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(_envelope_from_api(data))


@chat.function(
    "void_envelope",
    "Void a DocuSign envelope: cancels it for all recipients who have not yet completed signing, with a stated "
    "reason. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.void_envelope",
    effects=["docusign.envelope.voided"],
)
async def void_envelope(ctx, params: VoidEnvelopeParams) -> ActionResult:
    """Void a DocuSign envelope: cancels it for all recipients who have not yet completed signing, with a stated reason."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"status": "voided", "voidedReason": params.voided_reason or "Voided via Imperal"}
    try:
        data = await dc.request(ctx, conn, "PUT", f"/envelopes/{params.envelope_id}", json_body=body, action="void_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Envelope(id=params.envelope_id, status="voided"))


@chat.function(
    "resend_envelope",
    "Resend the signing-request notification email for an envelope to any recipients who have not yet acted.",
    action_type="write",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.resend_envelope",
    effects=["docusign.envelope.resent"],
)
async def resend_envelope(ctx, params: ResendEnvelopeParams) -> ActionResult:
    """Resend the signing-request notification email for an envelope to any recipients who have not yet acted."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await dc.request(ctx, conn, "PUT", f"/envelopes/{params.envelope_id}/recipients", params={"resend_envelope": "true"}, json_body={}, action="resend_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Envelope(id=params.envelope_id, status="resent"))


@chat.function(
    "correct_envelope",
    "Correct an in-progress (not yet completed) envelope's subject line and/or email message.",
    action_type="write",
    chain_callable=True,
    data_model=Envelope,
    event="docusign-connector.correct_envelope",
    effects=["docusign.envelope.corrected"],
)
async def correct_envelope(ctx, params: CorrectEnvelopeParams) -> ActionResult:
    """Correct an in-progress (not yet completed) envelope's subject line and/or email message."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body: dict = {}
    if params.email_subject.strip():
        body["emailSubject"] = params.email_subject
    if params.email_blurb.strip():
        body["emailBlurb"] = params.email_blurb
    if not body:
        return ActionResult.error("Provide a new subject and/or blurb to correct.", code="DOCUSIGN_MISSING_FIELDS")
    try:
        await dc.request(ctx, conn, "PUT", f"/envelopes/{params.envelope_id}", json_body=body, action="correct_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Envelope(id=params.envelope_id, status="corrected", email_subject=params.email_subject, email_blurb=params.email_blurb))


@chat.function(
    "list_envelope_documents",
    "List the documents attached to an envelope (id, name, type), including the Certificate of Completion.",
    action_type="read",
    chain_callable=True,
    data_model=EnvelopeDocumentList,
    event="docusign-connector.list_envelope_documents",
)
async def list_envelope_documents(ctx, params: EnvelopeScopedParams) -> ActionResult:
    """List the documents attached to an envelope (id, name, type), including the Certificate of Completion."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/envelopes/{params.envelope_id}/documents", action="list_envelope_documents")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    docs = data.get("envelopeDocuments", []) if isinstance(data, dict) else []
    return ActionResult.ok(EnvelopeDocumentList(items=[
        EnvelopeDocument(document_id=d.get("documentId", ""), name=d.get("name", ""), type=d.get("type", ""))
        for d in docs
    ]))


@chat.function(
    "get_envelope_document",
    "Download one document from a completed/in-progress envelope, base64-encoded ('combined' for the whole "
    "envelope as one PDF, or 'certificate' for the Certificate of Completion).",
    action_type="read",
    chain_callable=True,
    data_model=DocumentContent,
    event="docusign-connector.get_envelope_document",
)
async def get_envelope_document(ctx, params: GetEnvelopeDocumentParams) -> ActionResult:
    """Download one document from a completed/in-progress envelope, base64-encoded ('combined' for the whole envelope as one PDF, or 'certificate' for the Certificate of Completion)."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    tok = await dc.ensure_token(ctx, conn)
    if not tok.get("ok"):
        return ActionResult.error(tok.get("error", ""), code=tok.get("error_code"))
    url = f"{dc.rest_base(conn)}/envelopes/{params.envelope_id}/documents/{params.document_id}"
    resp = await ctx.http.get(url, headers={"Authorization": f"Bearer {tok['access_token']}", "Accept": "application/pdf"})
    if resp.status_code != 200:
        return ActionResult.error("Could not download this document.", code="DOCUSIGN_DOCUMENT_DOWNLOAD_FAILED")
    import base64
    raw = resp.body if isinstance(resp.body, (bytes, bytearray)) else str(resp.body).encode("utf-8", "ignore")
    return ActionResult.ok(DocumentContent(
        document_id=params.document_id,
        content_base64=base64.b64encode(raw).decode("ascii"),
        content_type=resp.headers.get("Content-Type", "application/pdf") if hasattr(resp, "headers") else "application/pdf",
    ))


@chat.function(
    "update_recipients",
    "Update recipient details (e.g. fix a mistyped email address) on an in-progress envelope before resending.",
    action_type="write",
    chain_callable=True,
    data_model=RecipientList,
    event="docusign-connector.update_recipients",
    effects=["docusign.envelope.recipients_updated"],
)
async def update_recipients(ctx, params: UpdateRecipientsParams) -> ActionResult:
    """Update recipient details (e.g."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        signers_in = json.loads(params.signers_json)
    except (TypeError, ValueError):
        return ActionResult.error("signers_json must be valid JSON.", code="DOCUSIGN_INVALID_JSON")
    body = {"signers": [{"recipientId": str(s.get("recipient_id", "")), "name": s.get("name", ""), "email": s.get("email", "")} for s in signers_in]}
    try:
        await dc.request(ctx, conn, "PUT", f"/envelopes/{params.envelope_id}/recipients", json_body=body, action="update_recipients")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(RecipientList(signers=[_signer_from_api({"recipientId": s["recipientId"], "name": s["name"], "email": s["email"]}) for s in body["signers"]]))


@chat.function(
    "add_recipient_tabs",
    "Attach signing fields (tabs) -- sign-here, initial-here, date-signed, text, checkbox, etc -- to a recipient "
    "on an in-progress envelope.",
    action_type="write",
    chain_callable=True,
    data_model=TabsResult,
    event="docusign-connector.add_recipient_tabs",
    effects=["docusign.envelope.tabs_added"],
)
async def add_recipient_tabs(ctx, params: AddRecipientTabsParams) -> ActionResult:
    """Attach signing fields (tabs) -- sign-here, initial-here, date-signed, text, checkbox, etc -- to a recipient on an in-progress envelope."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        tabs = json.loads(params.tabs_json)
    except (TypeError, ValueError):
        return ActionResult.error("tabs_json must be valid JSON.", code="DOCUSIGN_INVALID_JSON")
    try:
        data = await dc.request(ctx, conn, "POST", f"/envelopes/{params.envelope_id}/recipients/{params.recipient_id}/tabs", json_body=tabs, action="add_recipient_tabs")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(TabsResult(tabs_json=json.dumps(data)))


@chat.function(
    "list_recipient_tabs",
    "List the signing fields (tabs) currently attached to one recipient of an envelope.",
    action_type="read",
    chain_callable=True,
    data_model=TabsResult,
    event="docusign-connector.list_recipient_tabs",
)
async def list_recipient_tabs(ctx, params: ListRecipientTabsParams) -> ActionResult:
    """List the signing fields (tabs) currently attached to one recipient of an envelope."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/envelopes/{params.envelope_id}/recipients/{params.recipient_id}/tabs", action="list_recipient_tabs")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(TabsResult(tabs_json=json.dumps(data)))


@chat.function(
    "get_envelope_audit_events",
    "Get the tamper-evident audit trail (who viewed/signed/declined and when) for one envelope -- proof-of-process "
    "evidence for compliance.",
    action_type="read",
    chain_callable=True,
    data_model=AuditEventList,
    event="docusign-connector.get_envelope_audit_events",
)
async def get_envelope_audit_events(ctx, params: GetEnvelopeAuditEventsParams) -> ActionResult:
    """Get the tamper-evident audit trail (who viewed/signed/declined and when) for one envelope -- proof-of-process evidence for compliance."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/envelopes/{params.envelope_id}/audit_events", action="get_envelope_audit_events")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    events = data.get("auditEvents", []) if isinstance(data, dict) else []
    return ActionResult.ok(AuditEventList(items=[
        AuditEvent(event=e.get("eventFields", [{}])[0].get("value", "") if e.get("eventFields") else "", logged_at=e.get("logTime", ""), recipient_email="")
        for e in events
    ]))


@chat.function(
    "get_embedded_signing_url",
    "Generate a one-time embedded-signing URL for a recipient created with a clientUserId, so they can sign inside "
    "your own app/site instead of via email.",
    action_type="read",
    chain_callable=True,
    data_model=SigningUrlResult,
    event="docusign-connector.get_embedded_signing_url",
)
async def get_embedded_signing_url(ctx, params: GetSigningUrlParams) -> ActionResult:
    """Generate a one-time embedded-signing URL for a recipient created with a clientUserId, so they can sign inside your own app/site instead of via email."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.client_user_id.strip():
        return ActionResult.error("client_user_id is required for embedded signing -- it must match the value the recipient was created with.", code="DOCUSIGN_MISSING_FIELDS")
    body = {
        "returnUrl": params.return_url or "https://www.docusign.com",
        "authenticationMethod": "none",
        "email": "", "userName": "",
        "clientUserId": params.client_user_id,
        "recipientId": params.recipient_id,
    }
    try:
        data = await dc.request(ctx, conn, "POST", f"/envelopes/{params.envelope_id}/views/recipient", json_body=body, action="get_embedded_signing_url")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(SigningUrlResult(url=data.get("url", "")))
