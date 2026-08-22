"""Account/diagnostics chat functions for DocuSign Connector: account
info, billing plan, diagnostics (API request logging) settings, and
recipient-name search (autocomplete against past/known recipients).
Built on docusign_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import docusign_client as dc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    AccountInfo, BillingPlan, DiagnosticsSettings, RecipientNames,
    SearchRecipientNamesParams, ConnScopedParams,
)


@chat.function(
    "get_account_info",
    "Get basic information about the connected DocuSign account: account id, name, plan, and whether the "
    "impersonated user is an account administrator.",
    action_type="read",
    chain_callable=True,
    data_model=AccountInfo,
    event="docusign-connector.get_account_info",
)
async def get_account_info(ctx, params: ConnScopedParams) -> ActionResult:
    """Get basic information about the connected DocuSign account: account id, name, plan, and whether the impersonated user is an account administrator."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "", action="get_account_info")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    return ActionResult.ok(AccountInfo(
        account_id=conn.get("account_id", ""), account_name=data.get("accountName", "") or conn.get("account_name", ""),
        plan_name=data.get("planName", ""), is_admin=str(data.get("isDowngrade", "") == "" ),
    ))


@chat.function(
    "get_billing_plan",
    "Get this DocuSign account's billing plan and envelope usage (envelopes sent this period vs allowed).",
    action_type="read",
    chain_callable=True,
    data_model=BillingPlan,
    event="docusign-connector.get_billing_plan",
)
async def get_billing_plan(ctx, params: ConnScopedParams) -> ActionResult:
    """Get this DocuSign account's billing plan and envelope usage (envelopes sent this period vs allowed)."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/billing_plan", action="get_billing_plan")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    plan = data.get("planInformation", {}) if isinstance(data, dict) else {}
    return ActionResult.ok(BillingPlan(
        plan_name=data.get("planName", ""),
        envelopes_sent=str(plan.get("currentEnvelopeCount", "") or ""),
        envelopes_allowed=str(plan.get("allowedEnvelopeCount", "") or ""),
    ))


@chat.function(
    "get_diagnostics_settings",
    "Get this account's API request logging (diagnostics) settings -- whether Docusign is capturing raw API "
    "request/response logs for troubleshooting, and how many are stored.",
    action_type="read",
    chain_callable=True,
    data_model=DiagnosticsSettings,
    event="docusign-connector.get_diagnostics_settings",
)
async def get_diagnostics_settings(ctx, params: ConnScopedParams) -> ActionResult:
    """Get this account's API request logging (diagnostics) settings -- whether Docusign is capturing raw API request/response logs for troubleshooting, and how many are stored."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(ctx, conn, "GET", "/diagnostics/settings", action="get_diagnostics_settings")
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    try:
        logs = await dc.request(ctx, conn, "GET", "/diagnostics/request_logs", action="get_diagnostics_settings")
        log_count = str(len(logs.get("apiRequestLogs", []))) if isinstance(logs, dict) else "0"
    except dc.ClientFail:
        log_count = "0"
    return ActionResult.ok(DiagnosticsSettings(
        api_request_logging=str(data.get("apiRequestLogging", "")), log_count=log_count,
    ))


@chat.function(
    "search_recipient_names",
    "Search this account's known/past recipients by name or email fragment -- useful for autocompleting who to "
    "send an envelope to.",
    action_type="read",
    chain_callable=True,
    data_model=RecipientNames,
    event="docusign-connector.search_recipient_names",
)
async def search_recipient_names(ctx, params: SearchRecipientNamesParams) -> ActionResult:
    """Search this account's known/past recipients by name or email fragment -- useful for autocompleting who to send an envelope to."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        data = await dc.request(
            ctx, conn, "GET", "/recipient_names",
            params={"search_text": params.search_text} if params.search_text else None,
            action="search_recipient_names",
        )
    except dc.ClientFail as f:
        return ActionResult.error(f.message, code=f.payload.get("error_code"))
    names = data.get("names", []) if isinstance(data, dict) else []
    return ActionResult.ok(RecipientNames(matches=[n for n in names if isinstance(n, str)]))
