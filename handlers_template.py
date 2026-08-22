"""Template management chat functions for DocuSign Connector: create,
list/get, list documents, and delete. Built on docusign_client.py /
schemas.py, same shape as handlers_envelope.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    Template, TemplateList, GetTemplateParams, TemplateDocument,
    TemplateDocumentList, CreateTemplateParams, DeleteTemplateParams,
    ListParams, DeleteResult,
)


def _template_from_api(t: dict) -> Template:
    return Template(
        id=t.get("templateId", ""),
        name=t.get("name", ""),
        description=t.get("description", ""),
        shared=t.get("shared", ""),
        created_at=t.get("created", ""),
    )


@chat.function(
    "list_templates",
    "List templates available in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=TemplateList,
    event="docusign-connector.list_templates",
)
async def list_templates(ctx, params: ListParams) -> ActionResult:
    """List templates available in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/templates", params={"count": str(params.count)}, action="list_templates")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    templates = data.get("envelopeTemplates", []) if isinstance(data, dict) else []
    return ActionResult.ok(TemplateList(items=[_template_from_api(t) for t in templates]))


@chat.function(
    "get_template",
    "Get full details for one DocuSign template by id.",
    action_type="read",
    chain_callable=True,
    data_model=Template,
    event="docusign-connector.get_template",
)
async def get_template(ctx, params: GetTemplateParams) -> ActionResult:
    """Get full details for one DocuSign template by id."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/templates/{params.template_id}", action="get_template")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(_template_from_api(data))


@chat.function(
    "list_template_documents",
    "List the documents attached to a template (id, name).",
    action_type="read",
    chain_callable=True,
    data_model=TemplateDocumentList,
    event="docusign-connector.list_template_documents",
)
async def list_template_documents(ctx, params: GetTemplateParams) -> ActionResult:
    """List the documents attached to a template (id, name)."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/templates/{params.template_id}/documents", action="list_template_documents")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    docs = data.get("templateDocuments", []) if isinstance(data, dict) else []
    return ActionResult.ok(TemplateDocumentList(items=[
        TemplateDocument(document_id=d.get("documentId", ""), name=d.get("name", "")) for d in docs
    ]))


@chat.function(
    "create_template",
    "Create a reusable DocuSign template from a document, with named signer roles you can map to real people "
    "later with create_envelope_from_template.",
    action_type="write",
    chain_callable=True,
    data_model=Template,
    event="docusign-connector.create_template",
    effects=["docusign.template.created"],
)
async def create_template(ctx, params: CreateTemplateParams) -> ActionResult:
    """Create a reusable DocuSign template from a document, with named signer roles you can map to real people later with create_envelope_from_template."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.name.strip() or not params.document_base64.strip():
        return ActionResult.error("A name and a document are required.", code="DOCUSIGN_MISSING_FIELDS")
    try:
        roles_in = json.loads(params.roles_json) if params.roles_json.strip() else []
    except (TypeError, ValueError):
        return ActionResult.error("roles_json must be valid JSON.", code="DOCUSIGN_INVALID_JSON")
    roles = [{"roleName": r.get("role_name", ""), "routingOrder": str(r.get("routing_order") or "1")} for r in roles_in]
    body = {
        "name": params.name,
        "description": params.description,
        "documents": [{
            "documentBase64": params.document_base64,
            "name": params.document_name or "Document",
            "fileExtension": params.document_extension or "pdf",
            "documentId": "1",
        }],
        "recipients": {"signers": roles},
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/templates", json_body=body, action="create_template")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Template(id=data.get("templateId", ""), name=params.name, description=params.description))


@chat.function(
    "delete_template",
    "Permanently delete a DocuSign template. Envelopes already sent from it are unaffected. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.delete_template",
    effects=["docusign.template.deleted"],
)
async def delete_template(ctx, params: DeleteTemplateParams) -> ActionResult:
    """Permanently delete a DocuSign template."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await dc.request(ctx, conn, "DELETE", f"/templates/{params.template_id}", action="delete_template")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(DeleteResult(id=params.template_id, deleted=True))
