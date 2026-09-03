"""Panel UI -- connections list/connect form + consent-required banner.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as CircleCI
Connector's / Redox Connector's panels.py).

Every section (connections, connect form) is a plain ui.Stack, content
stacked vertically and left-aligned, sections separated by ui.Divider() --
no Card border/background/shadow anywhere in this slot. Disconnect lives
only in the "App settings" screen (panels_settings.py). The one secondary
"App settings" button is always the LAST element at the bottom of the
sidebar.

WHY A FOUR-FIELD JWT GRANT FORM, NOT A SINGLE TOKEN (unlike CircleCI) --
see app.py's module docstring for the full architectural reasoning:
DocuSign's own documented service-integration auth mechanism needs an
Integration Key, an impersonated User ID, and an RSA private key, plus
which environment (demo/production) to talk to.

PER ~/UI_INTERFACE_STANDARD.md (2026-08-21 addendum): every Input carries
its own visible label (never placeholder-only), the placeholder text is
always contextually specific to what's being entered (never a generic
"Enter value"), the form's own container is stretched to the full width
of the left sidebar, and the form's inner content is stretched to fill
that container. The "How do I set this up?" instruction lives ONLY in
the help modal (docusign_connect_help below) -- it is not duplicated as
static sidebar text.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers_connection as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", icon="settings", on_click=ui.Call("__panel__docusign_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or c.get("account_name") or "DocuSign account"
    env = c.get("environment", "demo")
    detail = f"{'Production' if env == 'production' else 'Demo/sandbox'} · account {c.get('account_id', '') or 'pending'}"
    children: list[ui.UINode] = [
        ui.Text(label, variant="body"),
        ui.Text(detail, variant="caption"),
    ]
    if c.get("consent_required"):
        children.append(ui.Alert(
            title="Consent required",
            message="Open the consent link below in a browser, log in as the impersonated user, and approve once.",
            type="warning",
        ))
        children.append(ui.Button(
            "Get consent link", variant="secondary", size="sm",
            on_click=ui.Call("get_consent_url", {"connection_id": c.get("id")}),
        ))
    return ui.Stack(direction="v", gap=1, children=children)


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No DocuSign accounts connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Form container stretched to the FULL WIDTH of the left sidebar, its
    inner content stretched to fill it (align="stretch" on both the outer
    Stack and the Form's own children Stack). No intro heading/description
    text here -- the JWT Grant walkthrough lives ONLY in
    docusign_connect_help's modal (button below opens it); repeating it
    here would duplicate that instruction."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I set this up?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__docusign_connect_help")),
        ui.Button("Log in with DocuSign (OAuth / JWT)", variant="primary", size="sm", icon="login"),
        ui.Divider(),
        ui.Text("Or connect via JWT Integration Key", variant="caption"),
        ui.Form(
            action="connect_docusign",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Environment", variant="caption"),
                    ui.Select(param_name="environment",
                              options=[
                                  {"label": "Demo / sandbox", "value": "demo"},
                                  {"label": "Production", "value": "production"},
                              ],
                              value="demo"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Integration Key", variant="caption"),
                    ui.Input(param_name="integration_key",
                             placeholder="Your app's Integration Key (client_id) from Apps and Keys"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Impersonated User ID", variant="caption"),
                    ui.Input(param_name="user_id",
                             placeholder="The DocuSign User ID (GUID) this connection sends/manages as"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("RSA Private Key (PEM)", variant="caption"),
                    ui.TextArea(param_name="private_key_pem",
                                placeholder="-----BEGIN RSA PRIVATE KEY-----\n...",
                                rows=6),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Label (optional)", variant="caption"),
                    ui.Input(param_name="label", placeholder="e.g. Sales team or HR onboarding"),
                ]),
            ],
        ),
    ])


@ext.panel("docusign_connect", slot="left", title="DocuSign", icon="✍️",
           default_width=340, min_width=280, max_width=440)
async def docusign_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    connected = bool(connections)

    header = ui.Header(text="DocuSign", level=2,
                        subtitle="Send, sign, and track agreements from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        ui.Text("Connected accounts", variant="subtitle"),
        _connections_section(connections),
        ui.Divider(),
        ui.Button("View envelope dashboard", variant="primary", size="sm", icon="FileSignature", on_click=ui.Call("__panel__docusign_center")),
        ui.Divider(),
        _connect_section(),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("docusign_connect_help", slot="center",
           title="How to connect DocuSign", center_overlay=True)
async def docusign_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. In DocuSign, go to Admin > Apps and Keys, and add an app (or use an existing one)."),
        ui.Text("2. Copy its Integration Key -- that's the client_id this form asks for."),
        ui.Text("3. Under that app, click \"Generate RSA\" -- copy the private key shown (DocuSign only shows it once) and paste it into the form here."),
        ui.Text("4. Find the User ID (GUID) of the account you want this connection to send/manage as, on that user's Admin profile page."),
        ui.Text("5. Connect here. If DocuSign reports consent is required, use the \"Get consent link\" button that appears, open it in a browser, log in as that same user, and approve once -- after that this connection works automatically."),
        ui.Divider(),
        ui.Alert(
            title="eSignature REST API v2.1 scope",
            message=(
                "This manages envelopes, templates, bulk send, PowerForms, "
                "folders, users/groups/permission profiles, brands, Connect "
                "webhooks, and account/diagnostics. The separate Rooms, "
                "Click, Admin, Monitor, Maestro, Navigator, and Web Forms "
                "APIs are out of scope."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Link(
            label="Open DocuSign's official JWT Grant guide",
            href="https://developers.docusign.com/platform/auth/jwt/",
        ),
    ])
    return ui.Dialog(
        title="How to connect DocuSign",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("docusign_center", slot="center", title="DocuSign", icon="✍️", center_overlay=True)
async def docusign_center_panel(ctx, envelope_id: str = "", **kwargs) -> object:
    """Post-connect main screen: an account health audit plus recent
    envelopes, or an envelope detail when `envelope_id` is passed
    (master-detail via the same panel_id, per UI_COMPONENT_VOCABULARY.md §3)."""
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(
            message="Connect a DocuSign account from the sidebar to see it here.",
            icon="✍️",
        )
    if envelope_id:
        return await _envelope_detail(ctx, envelope_id)
    return await _account_dashboard(ctx)


async def _account_dashboard(ctx) -> ui.UINode:
    import handlers_bulk_audit as hba
    import handlers_envelope as he
    from schemas import AuditAccountParams, ListParams

    body: list[ui.UINode] = []
    audit_result = await hba.audit_account_health(ctx, AuditAccountParams())
    if audit_result.success and audit_result.data:
        r = audit_result.data
        body.append(ui.Stats(children=[
            ui.Stat(label="Envelopes checked", value=str(r.total_envelopes_checked)),
            ui.Stat(label="Pending signature", value=str(r.pending_signature_count)),
            ui.Stat(label="Declined", value=str(r.declined_count)),
            ui.Stat(label="Voided", value=str(r.voided_count)),
        ]))
        if r.stuck_envelopes:
            body.append(ui.Alert(title="Stuck envelopes",
                                  message=f"{len(r.stuck_envelopes)} envelope(s) have been pending too long.",
                                  type="warning"))
        body.append(ui.Divider())

    body.append(ui.Text("Recent envelopes", variant="subtitle"))
    list_result = await he.list_envelopes(ctx, ListParams(count=20))
    envelopes = list_result.data.items if list_result.success and list_result.data else []
    if envelopes:
        columns = [
            ui.DataColumn("title", "Subject"),
            ui.DataColumn("status", "Status"),
            ui.DataColumn("sent_at", "Sent"),
        ]
        rows = [
            {"title": e.email_subject or e.title or e.id, "status": e.status,
             "sent_at": (e.sent_at or e.created_at or "")[:10] or "—", "envelope_id": e.id}
            for e in envelopes
        ]
        body.append(ui.DataTable(columns=columns, rows=rows,
                                  on_row_click=ui.Call("__panel__docusign_center", {"envelope_id": "{envelope_id}"})))
    else:
        body.append(ui.Text("No envelopes found on this account.", variant="caption"))
    return ui.Stack(direction="v", gap=3, align="stretch", children=body)


async def _envelope_detail(ctx, envelope_id: str) -> ui.UINode:
    import handlers_envelope as he
    from schemas import EnvelopeScopedParams
    result = await he.get_envelope(ctx, EnvelopeScopedParams(envelope_id=envelope_id))
    if not result.success or not result.data:
        return ui.Stack(direction="v", gap=3, align="stretch", children=[
            ui.Button("← Back to envelopes", variant="ghost", size="sm",
                      on_click=ui.Call("__panel__docusign_center")),
            ui.Alert(title="Could not load this envelope",
                     message=result.error or "It may have been deleted or you lack access.", type="error"),
        ])
    e = result.data
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("← Back to envelopes", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__docusign_center")),
        ui.Header(text=e.email_subject or e.title or envelope_id, level=3),
        ui.KeyValue(columns=2, items=[
            {"key": "Status", "value": e.status},
            {"key": "Sent", "value": e.sent_at or "—"},
            {"key": "Completed", "value": e.completed_at or "—"},
            {"key": "Signers", "value": str(len(e.signers))},
        ]),
    ])
