"""Brand management chat functions for DocuSign Connector: list an
account's visual brands and apply one to an envelope's emails/signing
pages. Built on docusign_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import Brand, BrandList, ApplyBrandToEnvelopeParams, ConnScopedParams


@chat.function(
    "list_brands",
    "List visual brands (logo, colors, custom email/signing text) configured in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=BrandList,
    event="docusign-connector.list_brands",
)
async def list_brands(ctx, params: ConnScopedParams) -> ActionResult:
    """List visual brands (logo, colors, custom email/signing text) configured in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/brands", action="list_brands")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("brands", []) if isinstance(data, dict) else []
    return ActionResult.success(BrandList(items=[
        Brand(id=b.get("brandId", ""), name=b.get("brandName", ""), is_default=b.get("isSendingDefault", ""))
        for b in items
    ]), summary="Brands listed.")


@chat.function(
    "apply_brand_to_envelope",
    "Apply a saved brand (logo, colors, custom text) to a specific envelope's emails and signing pages.",
    action_type="write",
    chain_callable=True,
    data_model=Brand,
    event="docusign-connector.apply_brand_to_envelope",
    effects=["docusign.envelope.branded"],
)
async def apply_brand_to_envelope(ctx, params: ApplyBrandToEnvelopeParams) -> ActionResult:
    """Apply a saved brand (logo, colors, custom text) to a specific envelope's emails and signing pages."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"emailSettings": {"brandId": params.brand_id}, "brandId": params.brand_id}
    try:
        await dc.request(ctx, conn, "PUT", f"/envelopes/{params.envelope_id}", json_body=body, action="apply_brand_to_envelope")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.success(Brand(id=params.brand_id), summary="Apply brand to envelope done.")
