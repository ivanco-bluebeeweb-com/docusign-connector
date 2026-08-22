"""Folders chat functions for DocuSign Connector: organize envelopes into
folders and move envelopes between them. Built on docusign_client.py /
schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from handlers_envelope import _envelope_from_api
from schemas import (
    Folder, FolderList, ListFolderItemsParams, EnvelopeList,
    MoveEnvelopeToFolderParams, ConnScopedParams,
)


@chat.function(
    "list_folders",
    "List folders used to organize envelopes in this DocuSign account (e.g. 'Drafts', 'Sent', 'Completed', and any "
    "custom folders).",
    action_type="read",
    chain_callable=True,
    data_model=FolderList,
    event="docusign-connector.list_folders",
)
async def list_folders(ctx, params: ConnScopedParams) -> ActionResult:
    """List folders used to organize envelopes in this DocuSign account (e.g."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/folders", action="list_folders")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("folders", []) if isinstance(data, dict) else []
    return ActionResult.ok(FolderList(items=[
        Folder(id=fo.get("folderId", ""), name=fo.get("name", ""), item_count=str(fo.get("itemCount", "") or ""))
        for fo in items
    ]))


@chat.function(
    "list_folder_items",
    "List envelopes filed inside a specific DocuSign folder.",
    action_type="read",
    chain_callable=True,
    data_model=EnvelopeList,
    event="docusign-connector.list_folder_items",
)
async def list_folder_items(ctx, params: ListFolderItemsParams) -> ActionResult:
    """List envelopes filed inside a specific DocuSign folder."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", f"/folders/{params.folder_id}", action="list_folder_items")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("folderItems", []) if isinstance(data, dict) else []
    return ActionResult.ok(EnvelopeList(items=[_envelope_from_api(e) for e in items]))


@chat.function(
    "move_envelope_to_folder",
    "Move an envelope into a different DocuSign folder.",
    action_type="write",
    chain_callable=True,
    data_model=Folder,
    event="docusign-connector.move_envelope_to_folder",
    effects=["docusign.envelope.moved"],
)
async def move_envelope_to_folder(ctx, params: MoveEnvelopeToFolderParams) -> ActionResult:
    """Move an envelope into a different DocuSign folder."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"envelopeIds": [params.envelope_id]}
    try:
        await dc.request(ctx, conn, "PUT", f"/folders/{params.folder_id}", json_body=body, action="move_envelope_to_folder")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Folder(id=params.folder_id))
