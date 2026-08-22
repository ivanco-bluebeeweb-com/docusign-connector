"""Pydantic params models + SDL entity contracts for DocuSign Connector.

All params models are module-scope (V17 federal invariant, same rule as
CircleCI Connector's / Redox Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectDocusignParams(BaseModel):
    environment: str = Field(
        "demo",
        description="Which DocuSign environment to authenticate against: 'demo' (developer sandbox, account-d.docusign.com) or 'production' (account.docusign.com).",
    )
    integration_key: str = Field(
        "",
        description="Your DocuSign Integration Key (client_id) from the app you registered at admin.docusign.com > Apps and Keys.",
    )
    user_id: str = Field(
        "",
        description="The DocuSign User ID (GUID, found on the same user's Admin profile page) to impersonate -- the account this connector sends/manages envelopes as.",
    )
    private_key_pem: str = Field(
        "",
        description="The RSA private key PEM you generated for this Integration Key (Apps and Keys > your app > Generate RSA). Never displayed back after saving.",
    )
    label: str = Field("", description="Optional friendly name for this connection (e.g. 'Sales team' or 'HR onboarding').")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""
    environment: str = ""
    account_id: str = ""
    consent_required: bool = False


class ProviderConnectionList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[ProviderConnection] = []


class DisconnectDocusignParams(BaseModel):
    connection_id: str = Field("", description="Id of the connection to disconnect (from list_connections).")


class DeleteResult(sdl.Entity):
    title: str = ""
    id: str = ""
    deleted: bool = False


class GetConsentUrlParams(BaseModel):
    connection_id: str = Field("", description="Id of a saved connection to build the one-time admin consent URL for.")


class ConsentUrlResult(sdl.Entity):
    id: str = ""
    title: str = ""
    consent_url: str = ""
    environment: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Shared scoping params
# ──────────────────────────────────────────────────────────────────────────


class ConnScopedParams(BaseModel):
    connection_id: str = ""


class EnvelopeScopedParams(BaseModel):
    envelope_id: str = Field("", description="The DocuSign envelope id (GUID) to act on.")
    connection_id: str = ""


class TemplateScopedParams(BaseModel):
    template_id: str = Field("", description="The DocuSign template id (GUID) to act on.")
    connection_id: str = ""


class ListParams(BaseModel):
    from_date: str = Field("", description="Optional ISO date (YYYY-MM-DD) to filter items created/modified on or after this date.")
    status: str = Field("", description="Optional status filter, e.g. 'sent', 'completed', 'declined', 'voided'.")
    count: int = Field(25, description="Max number of items to return (DocuSign default page size).")
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Envelopes
# ──────────────────────────────────────────────────────────────────────────


class Signer(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    email: str = ""
    recipient_id: str = ""
    routing_order: str = ""
    status: str = ""


class Envelope(sdl.Entity):
    title: str = ""
    id: str = ""
    status: str = ""
    email_subject: str = ""
    email_blurb: str = ""
    sent_at: str = ""
    completed_at: str = ""
    created_at: str = ""
    signers: list[Signer] = []


class EnvelopeList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[Envelope] = []
    total_set_size: str = ""


class CreateEnvelopeParams(BaseModel):
    email_subject: str = Field("", description="Subject line of the email DocuSign sends to recipients, e.g. 'Please sign: Q3 Services Agreement'.")
    email_blurb: str = Field("", description="Short message body shown above the signing link in the notification email.")
    document_base64: str = Field("", description="The document to send, base64-encoded (PDF/Word/etc).")
    document_name: str = Field("", description="File name shown to the recipient, e.g. 'Services Agreement.pdf'.")
    document_extension: str = Field("pdf", description="File extension of the document, e.g. 'pdf', 'docx'.")
    signers_json: str = Field(
        "",
        description='JSON array of signers, e.g. [{"name":"Jane Doe","email":"jane@example.com","recipient_id":"1","routing_order":"1"}].',
    )
    cc_json: str = Field(
        "",
        description='Optional JSON array of CC recipients (receive a copy, do not sign), e.g. [{"name":"Manager","email":"mgr@example.com","recipient_id":"2"}].',
    )
    status: str = Field("sent", description="'sent' to send immediately, or 'created' to save as a draft envelope.")
    connection_id: str = ""


class CreateEnvelopeFromTemplateParams(BaseModel):
    template_id: str = Field("", description="The DocuSign template id (GUID) to send from.")
    email_subject: str = Field("", description="Subject line of the email DocuSign sends to recipients.")
    template_roles_json: str = Field(
        "",
        description='JSON array mapping template roles to real people, e.g. [{"role_name":"Signer 1","name":"Jane Doe","email":"jane@example.com"}].',
    )
    status: str = Field("sent", description="'sent' to send immediately, or 'created' to save as a draft envelope.")
    connection_id: str = ""


class VoidEnvelopeParams(BaseModel):
    envelope_id: str = ""
    voided_reason: str = Field("", description="Reason shown to recipients for why this envelope was voided, e.g. 'Sent in error, please disregard.'")
    connection_id: str = ""


class ResendEnvelopeParams(BaseModel):
    envelope_id: str = ""
    connection_id: str = ""


class CorrectEnvelopeParams(BaseModel):
    envelope_id: str = ""
    email_subject: str = Field("", description="New subject line to correct the envelope with (leave blank to keep unchanged).")
    email_blurb: str = Field("", description="New email message to correct the envelope with (leave blank to keep unchanged).")
    connection_id: str = ""


class EnvelopeDocument(sdl.Entity):
    id: str = ""
    title: str = ""
    document_id: str = ""
    name: str = ""
    type: str = ""


class EnvelopeDocumentList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[EnvelopeDocument] = []


class GetEnvelopeDocumentParams(BaseModel):
    envelope_id: str = ""
    document_id: str = Field("combined", description="The document id to download, or 'combined' for the whole envelope as one PDF, or 'certificate' for the Certificate of Completion.")
    connection_id: str = ""


class DocumentContent(sdl.Entity):
    id: str = ""
    title: str = ""
    document_id: str = ""
    content_base64: str = ""
    content_type: str = ""


class RecipientList(sdl.Entity):
    id: str = ""
    title: str = ""
    signers: list[Signer] = []


class UpdateRecipientsParams(BaseModel):
    envelope_id: str = ""
    signers_json: str = Field("", description="JSON array of signer objects to update (must include recipient_id), e.g. to correct an email address before resending.")
    connection_id: str = ""


class AddRecipientTabsParams(BaseModel):
    envelope_id: str = ""
    recipient_id: str = Field("", description="The recipient_id (from the envelope's recipients) to attach fields to.")
    tabs_json: str = Field(
        "",
        description='JSON object of tab arrays keyed by type, e.g. {"signHereTabs":[{"documentId":"1","pageNumber":"1","xPosition":"100","yPosition":"100"}]}.',
    )
    connection_id: str = ""


class ListRecipientTabsParams(BaseModel):
    envelope_id: str = ""
    recipient_id: str = ""
    connection_id: str = ""


class TabsResult(sdl.Entity):
    id: str = ""
    title: str = ""
    tabs_json: str = ""


class GetEnvelopeAuditEventsParams(BaseModel):
    envelope_id: str = ""
    connection_id: str = ""


class AuditEvent(sdl.Entity):
    id: str = ""
    title: str = ""
    event: str = ""
    logged_at: str = ""
    recipient_email: str = ""


class AuditEventList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[AuditEvent] = []


class GetSigningUrlParams(BaseModel):
    envelope_id: str = ""
    recipient_id: str = Field("", description="The recipient_id to generate an embedded-signing URL for.")
    return_url: str = Field("", description="Where DocuSign redirects the signer after they finish signing (e.g. your own thank-you page).")
    client_user_id: str = Field("", description="The clientUserId this recipient was created with (required for embedded signing -- must match exactly).")
    connection_id: str = ""


class SigningUrlResult(sdl.Entity):
    id: str = ""
    title: str = ""
    url: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Bulk send
# ──────────────────────────────────────────────────────────────────────────


class CreateBulkSendListParams(BaseModel):
    name: str = Field("", description="Name for this bulk recipient list, e.g. 'Q3 Vendor NDAs'.")
    recipients_json: str = Field(
        "",
        description='JSON array of recipient rows, e.g. [{"name":"Jane Doe","email":"jane@example.com","role_name":"Signer 1"}].',
    )
    connection_id: str = ""


class BulkList(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    recipient_count: str = ""


class BulkListList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[BulkList] = []


class SendBulkEnvelopeParams(BaseModel):
    bulk_list_id: str = Field("", description="The bulk recipient list id to send to (from create_bulk_send_list).")
    template_id: str = Field("", description="The template to use as the envelope base for every recipient in the list.")
    email_subject: str = Field("", description="Subject line of the email DocuSign sends to every recipient.")
    connection_id: str = ""


class BulkSendResult(sdl.Entity):
    id: str = ""
    title: str = ""
    batch_id: str = ""
    envelope_or_template_id: str = ""


class GetBulkSendBatchStatusParams(BaseModel):
    batch_id: str = ""
    connection_id: str = ""


class BulkSendBatchStatus(sdl.Entity):
    id: str = ""
    title: str = ""
    batch_id: str = ""
    status: str = ""
    envelopes_sent: str = ""
    envelopes_failed: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────────────────────────────────


class Template(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    description: str = ""
    shared: str = ""
    created_at: str = ""


class TemplateList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[Template] = []


class GetTemplateParams(BaseModel):
    template_id: str = ""
    connection_id: str = ""


class TemplateDocument(sdl.Entity):
    id: str = ""
    title: str = ""
    document_id: str = ""
    name: str = ""


class TemplateDocumentList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[TemplateDocument] = []


class CreateTemplateParams(BaseModel):
    name: str = Field("", description="Name shown for this template in the DocuSign template library, e.g. 'Standard NDA'.")
    description: str = Field("", description="Short description of when to use this template.")
    document_base64: str = Field("", description="The base document for this template, base64-encoded (PDF/Word/etc).")
    document_name: str = Field("", description="File name for the template document, e.g. 'NDA.pdf'.")
    document_extension: str = Field("pdf", description="File extension of the document, e.g. 'pdf', 'docx'.")
    roles_json: str = Field(
        "",
        description='JSON array of template signer roles, e.g. [{"role_name":"Signer 1","routing_order":"1"}].',
    )
    connection_id: str = ""


class DeleteTemplateParams(BaseModel):
    template_id: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# PowerForms
# ──────────────────────────────────────────────────────────────────────────


class PowerForm(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    url: str = ""
    is_active: str = ""


class PowerFormList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[PowerForm] = []


class CreatePowerFormParams(BaseModel):
    name: str = Field("", description="Name of this self-service signing form, e.g. 'New Hire NDA (self-serve)'.")
    template_id: str = Field("", description="The template this PowerForm is built from.")
    email_subject: str = Field("", description="Subject line used for the confirmation email once someone signs via this form.")
    connection_id: str = ""


class DeletePowerFormParams(BaseModel):
    powerform_id: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Folders
# ──────────────────────────────────────────────────────────────────────────


class Folder(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    item_count: str = ""


class FolderList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[Folder] = []


class ListFolderItemsParams(BaseModel):
    folder_id: str = ""
    connection_id: str = ""


class MoveEnvelopeToFolderParams(BaseModel):
    envelope_id: str = ""
    folder_id: str = Field("", description="The destination folder id to move this envelope into.")
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Users / groups / permission profiles
# ──────────────────────────────────────────────────────────────────────────


class DocusignUser(sdl.Entity):
    title: str = ""
    id: str = ""
    user_name: str = ""
    email: str = ""
    user_status: str = ""


class DocusignUserList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[DocusignUser] = []


class CreateUserParams(BaseModel):
    user_name: str = Field("", description="Full display name for the new DocuSign account user, e.g. 'Jane Doe'.")
    email: str = Field("", description="Email address of the new account user -- DocuSign sends their activation email here.")
    connection_id: str = ""


class DeleteUserParams(BaseModel):
    user_id: str = ""
    connection_id: str = ""


class Group(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    user_count: str = ""


class GroupList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[Group] = []


class CreateGroupParams(BaseModel):
    group_name: str = Field("", description="Name for the new permission/routing group, e.g. 'Sales EMEA'.")
    connection_id: str = ""


class AddUsersToGroupParams(BaseModel):
    group_id: str = ""
    user_ids_json: str = Field("", description='JSON array of DocuSign user ids to add to this group, e.g. ["id-1","id-2"].')
    connection_id: str = ""


class PermissionProfile(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""


class PermissionProfileList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[PermissionProfile] = []


# ──────────────────────────────────────────────────────────────────────────
# Brands
# ──────────────────────────────────────────────────────────────────────────


class Brand(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    is_default: str = ""


class BrandList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[Brand] = []


class ApplyBrandToEnvelopeParams(BaseModel):
    envelope_id: str = ""
    brand_id: str = Field("", description="The brand id to apply to this envelope's emails and signing pages.")
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Connect (webhooks)
# ──────────────────────────────────────────────────────────────────────────


class ConnectConfig(sdl.Entity):
    title: str = ""
    id: str = ""
    name: str = ""
    url_to_publish_to: str = ""
    enabled: str = ""
    events_json: str = ""


class ConnectConfigList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[ConnectConfig] = []


class CreateConnectWebhookParams(BaseModel):
    name: str = Field("", description="Friendly name for this Connect (webhook) configuration, e.g. 'Envelope status to Imperal'.")
    url_to_publish_to: str = Field("", description="HTTPS endpoint DocuSign will POST envelope/recipient events to.")
    events_json: str = Field(
        "",
        description='JSON array of envelope-level events to subscribe to, e.g. ["envelope-sent","envelope-completed","envelope-declined","envelope-voided"].',
    )
    include_documents: bool = Field(False, description="Whether DocuSign should include the signed documents themselves in each webhook payload (larger payloads).")
    connection_id: str = ""


class UpdateConnectWebhookParams(BaseModel):
    connect_id: str = ""
    name: str = Field("", description="New friendly name (leave blank to keep unchanged).")
    url_to_publish_to: str = Field("", description="New HTTPS endpoint (leave blank to keep unchanged).")
    enabled: str = Field("", description="'true' or 'false' to enable/disable this Connect configuration (leave blank to keep unchanged).")
    connection_id: str = ""


class DeleteConnectWebhookParams(BaseModel):
    connect_id: str = ""
    connection_id: str = ""


class ConnectLog(sdl.Entity):
    id: str = ""
    title: str = ""
    connect_id: str = ""
    status: str = ""
    logged_at: str = ""
    envelope_id: str = ""


class ConnectLogList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[ConnectLog] = []


class GetConnectFailuresParams(BaseModel):
    connection_id: str = ""


class RetryConnectFailureParams(BaseModel):
    failure_id: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Account / diagnostics
# ──────────────────────────────────────────────────────────────────────────


class AccountInfo(sdl.Entity):
    id: str = ""
    title: str = ""
    account_id: str = ""
    account_name: str = ""
    plan_name: str = ""
    is_admin: str = ""


class BillingPlan(sdl.Entity):
    id: str = ""
    title: str = ""
    plan_name: str = ""
    envelopes_sent: str = ""
    envelopes_allowed: str = ""


class DiagnosticsSettings(sdl.Entity):
    id: str = ""
    title: str = ""
    api_request_logging: str = ""
    log_count: str = ""


class RecipientNames(sdl.Entity):
    id: str = ""
    title: str = ""
    matches: list[str] = []


class SearchRecipientNamesParams(BaseModel):
    search_text: str = Field("", description="Name or email fragment to search for among this account's known/past recipients.")
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Bulk operations + audit (Ярус 3 value-add)
# ──────────────────────────────────────────────────────────────────────────


class BulkResultItem(sdl.Entity):
    title: str = ""
    id: str = ""
    ok: bool = False
    error: str = ""


class BulkResult(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[BulkResultItem] = []
    succeeded: int = 0
    failed: int = 0


class BulkVoidEnvelopesParams(BaseModel):
    envelope_ids_json: str = Field("", description='JSON array of envelope ids to void in one call, e.g. ["id-1","id-2"].')
    voided_reason: str = Field("", description="Reason shown to recipients for why these envelopes were voided.")
    connection_id: str = ""


class BulkResendEnvelopesParams(BaseModel):
    envelope_ids_json: str = Field("", description='JSON array of envelope ids to resend reminder notifications for, e.g. ["id-1","id-2"].')
    connection_id: str = ""


class AuditAccountParams(BaseModel):
    connection_id: str = ""


class AccountHealthReport(sdl.Entity):
    id: str = ""
    title: str = ""
    total_envelopes_checked: int = 0
    pending_signature_count: int = 0
    declined_count: int = 0
    voided_count: int = 0
    stuck_envelopes: list[str] = []
    expiring_soon: list[str] = []
    notes: list[str] = []
