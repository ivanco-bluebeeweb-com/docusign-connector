"""User/group/permission-profile administration chat functions for
DocuSign Connector (account-level admin, not the Admin API product --
these are the eSignature REST API's own /users, /groups,
/permission_profiles resources). Built on docusign_client.py / schemas.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    DocusignUser, DocusignUserList, CreateUserParams, DeleteUserParams,
    Group, GroupList, CreateGroupParams, AddUsersToGroupParams,
    PermissionProfile, PermissionProfileList, ConnScopedParams, DeleteResult,
)


@chat.function(
    "list_account_users",
    "List users in this DocuSign account (name, email, status -- active/pending/closed).",
    action_type="read",
    chain_callable=True,
    data_model=DocusignUserList,
    event="docusign-connector.list_account_users",
)
async def list_account_users(ctx, params: ConnScopedParams) -> ActionResult:
    """List users in this DocuSign account (name, email, status -- active/pending/closed)."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/users", action="list_account_users")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("users", []) if isinstance(data, dict) else []
    return ActionResult.ok(DocusignUserList(items=[
        DocusignUser(id=u.get("userId", ""), user_name=u.get("userName", ""), email=u.get("email", ""), user_status=u.get("userStatus", ""))
        for u in items
    ]))


@chat.function(
    "create_account_user",
    "Add a new user to this DocuSign account -- DocuSign emails them an activation link.",
    action_type="write",
    chain_callable=True,
    data_model=DocusignUser,
    event="docusign-connector.create_account_user",
    effects=["docusign.user.created"],
)
async def create_account_user(ctx, params: CreateUserParams) -> ActionResult:
    """Add a new user to this DocuSign account -- DocuSign emails them an activation link."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"newUsers": [{"userName": params.user_name, "email": params.email}]}
    try:
        data = await dc.request(ctx, conn, "POST", "/users", json_body=body, action="create_account_user")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    created = (data.get("newUsers") or [{}])[0] if isinstance(data, dict) else {}
    return ActionResult.ok(DocusignUser(
        id=created.get("userId", ""), user_name=params.user_name, email=params.email,
        user_status=created.get("userStatus", ""),
    ))


@chat.function(
    "delete_account_user",
    "Remove (close) a user's access to this DocuSign account.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="docusign-connector.delete_account_user",
    effects=["docusign.user.deleted"],
)
async def delete_account_user(ctx, params: DeleteUserParams) -> ActionResult:
    """Remove (close) a user's access to this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"users": [{"userId": params.user_id}]}
    try:
        await dc.request(ctx, conn, "DELETE", "/users", json_body=body, action="delete_account_user")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(DeleteResult(id=params.user_id, deleted=True))


@chat.function(
    "list_groups",
    "List permission/routing groups configured in this DocuSign account.",
    action_type="read",
    chain_callable=True,
    data_model=GroupList,
    event="docusign-connector.list_groups",
)
async def list_groups(ctx, params: ConnScopedParams) -> ActionResult:
    """List permission/routing groups configured in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/groups", action="list_groups")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("groups", []) if isinstance(data, dict) else []
    return ActionResult.ok(GroupList(items=[
        Group(id=g.get("groupId", ""), name=g.get("groupName", ""), user_count=str(g.get("usersCount", "") or ""))
        for g in items
    ]))


@chat.function(
    "create_group",
    "Create a new permission/routing group in this DocuSign account.",
    action_type="write",
    chain_callable=True,
    data_model=Group,
    event="docusign-connector.create_group",
    effects=["docusign.group.created"],
)
async def create_group(ctx, params: CreateGroupParams) -> ActionResult:
    """Create a new permission/routing group in this DocuSign account."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    body = {"groups": [{"groupName": params.group_name}]}
    try:
        data = await dc.request(ctx, conn, "POST", "/groups", json_body=body, action="create_group")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    created = (data.get("groups") or [{}])[0] if isinstance(data, dict) else {}
    return ActionResult.ok(Group(id=created.get("groupId", ""), name=params.group_name, user_count="0"))


@chat.function(
    "add_users_to_group",
    "Add one or more existing account users to a permission/routing group.",
    action_type="write",
    chain_callable=True,
    data_model=Group,
    event="docusign-connector.add_users_to_group",
    effects=["docusign.group.membership_updated"],
)
async def add_users_to_group(ctx, params: AddUsersToGroupParams) -> ActionResult:
    """Add one or more existing account users to a permission/routing group."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        user_ids = json.loads(params.user_ids_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("user_ids_json must be a valid JSON array.", code="DOCUSIGN_INVALID_JSON")
    body = {"users": [{"userId": uid} for uid in user_ids]}
    try:
        await dc.request(ctx, conn, "PUT", f"/groups/{params.group_id}/users", json_body=body, action="add_users_to_group")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(Group(id=params.group_id))


@chat.function(
    "list_permission_profiles",
    "List permission profiles (roles) available in this DocuSign account -- what a user is allowed to do, e.g. "
    "Account Administrator, Sender, Viewer.",
    action_type="read",
    chain_callable=True,
    data_model=PermissionProfileList,
    event="docusign-connector.list_permission_profiles",
)
async def list_permission_profiles(ctx, params: ConnScopedParams) -> ActionResult:
    """List permission profiles (roles) available in this DocuSign account -- what a user is allowed to do, e.g."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/permission_profiles", action="list_permission_profiles")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    items = data.get("permissionProfiles", []) if isinstance(data, dict) else []
    return ActionResult.ok(PermissionProfileList(items=[
        PermissionProfile(id=p.get("permissionProfileId", ""), name=p.get("permissionProfileName", ""))
        for p in items
    ]))
