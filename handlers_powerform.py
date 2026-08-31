"""PowerForms chat functions for DocuSign Connector: self-service signing
forms built from a template -- a public URL anyone can visit to fill in
and sign without the sender manually creating an envelope per person.
Built on docusign_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    PowerForm, PowerFormList, CreatePowerFormParams, DeletePowerFormParams,
    ConnScopedParams, DeleteResult,
)


def _powerform_from_api(p: dict) -> PowerForm:
    return PowerForm(
        id=p.get("powerFormId", ""), name=p.get("name", ""),
        url=p.get("senderViewUrl", "") or p.get("url", ""),
        is_active=p.get("isActive", ""),
    )


@chat.function(
    "create_powerform",
    "Create a DocuSign PowerForm from a template: a public self-service signing link you can share (embed on a "
    "website, put in a support ticket macro, etc) so recipients fill in and sign without you sending an envelope "
    "to each person individually.",
    action_type="write",
    chain_callable=True,
    data_model=PowerForm,
    event="docusign-connector.create_powerform",
    effects=["docusign.powerform.created"],
)
async def create_powerform(ctx, params: CreatePowerFormParams) -> ActionResult:
    """Create a DocuSign PowerForm from a template: a public self-service signing link you can share (embed on a website, put in a support ticket macro, etc) so recipients fill in and sign without you sending an envelope to each person individually."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {
        "name": params.name,
        "templateId": params.template_id,
        "emailSubject": params.email_subject,
        "isActive": "true",
        "signingMode": "email",
    }
    try:
        data = await dc.request(ctx, conn, "POST", "/powerforms", json_body=body, action="create_powerform")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(_powerform_from_api(data), summary="Powerform created.")


@chat.function(
    "list_powerforms",
    "List PowerForms (self-service signing links) configured in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=PowerFormList,
    event="docusign-connector.list_powerforms",
)
async def list_powerforms(ctx, params: ConnScopedParams) -> ActionResult:
    """List PowerForms (self-service signing links) configured in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/powerforms", action="list_powerforms")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("powerFormsList", []) if isinstance(data, dict) else []
    return ActionResult.success(PowerFormList(items=[_powerform_from_api(p) for p in items]), summary="Powerforms listed.")


@chat.function(
    "delete_powerform",
    "Delete (deactivate) a DocuSign PowerForm so its public signing link stops accepting new signers.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.delete_powerform",
    effects=["docusign.powerform.deleted"],
)
async def delete_powerform(ctx, params: DeletePowerFormParams) -> ActionResult:
    """Delete (deactivate) a DocuSign PowerForm so its public signing link stops accepting new signers."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await dc.request(ctx, conn, "DELETE", "/powerforms", json_body={"powerFormsId": [params.powerform_id]}, action="delete_powerform")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(DeleteResult(id=params.powerform_id, deleted=True), summary="Powerform deleted.")
