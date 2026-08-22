# DocuSign Connector — Preparation

**Статус:** Фаза 1 (Discovery + архитектурные решения) завершена. Объём
релиза заявлен пользователем явно в исходном запросе задачи #2263 —
"разработай это приложение в максимальной форме со всеми доступными
функциями с их стороны и всеми возможными функциями внутри нашего
приложения" — трактуется как "максимум" (Ярус 1+2+3), по прецеденту
CircleCI/GitLab CI/CD/MuleSoft/Power Automate/UiPath/Blue Prism/Automation
Anywhere/Cin7 Core/ShipStation/PagerDuty, где такая же явная формулировка в
задаче уже освобождала от повторного вопроса.

**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-22, v0.1
**Vikunja task:** #2263 (BBW Imperal Apps), [App Development].

**Почему сейчас:** DocuSign — рыночный лидер e-signature/agreement
management, стандарт де-факто для юридически значимого подписания
документов. В портфеле Imperal нет ни одного e-signature/agreement-
lifecycle коннектора — закрывает нишу клиентов, которым нужно
отправлять/отслеживать/архивировать подписываемые договоры, NDA, HR-
документы прямо из Imperal.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «DocuSign»**. Внутренний
app_id/папка: `docusign-connector`.

**DocuSign Connector** — коннектор к DocuSign eSignature REST API v2.1
(`developers.docusign.com/docs/esign-rest-api`), покрывающий весь домен
подготовки/отправки/подписания/архивации документов: envelopes (создание,
отправка, статус, документы, получатели, поля/tabs, голосовая аутентификация,
correct/void/resend), templates (создание, шаблонные документы, шаблонные
получатели/поля), bulk send (массовая рассылка одного конверта многим
получателям через bulk lists), PowerForms (самообслуживаемые публичные
формы подписания), folders (организация конвертов), users/groups/permission
profiles (администрирование аккаунта), brands (визуальный брендинг писем и
подписи), Connect webhooks (событийные уведомления вместо polling), custom
tabs (переиспользуемые поля), diagnostics/request logging, BCC email archive,
payments внутри конверта. BYOK: пользователь подключает свой собственный
DocuSign Integration Key (JWT Grant с RSA keypair) к своему собственному
DocuSign-аккаунту. Imperal ничего не хостит и не проксирует помимо самого
запроса.

**Сознательно вне охвата:** Rooms API (real estate transaction rooms,
отдельный лицензируемый продукт DocuSign Rooms); Click API (clickwrap
"I agree" виджеты, отдельный продукт DocuSign Click); Admin API
(организационное управление на уровне DocuSign Organization, а не
Account — Enterprise Org Admin функционал); Monitor API (событийный
compliance/SIEM аудит-лог, отдельный продукт Monitor); Maestro API
(no-code workflow-оркестрация поверх eSignature, отдельный бета/GA
продукт); Navigator API (AI-агрегация метаданных контрактов, отдельный
продукт); Web Forms API (отдельный от PowerForms продукт с собственным
конструктором); eNotary (Legacy — DocuSign сам маркирует устаревшим);
Workspaces (устаревший коллаборационный модуль, DocuSign рекомендует Rooms
вместо него, которого тоже нет в охвате) — см. CONNECTOR_DISCOVERY.md §2
для полного обоснования каждого исключения (тот же принцип, что исключения
Salesforce Metadata/Tooling/Streaming API).

## 2. Архитектурное решение: BYOK, JWT Grant (service integration)

**WHY BYOK**, та же логика, что Salesforce/MuleSoft/Stripe/CircleCI
Connector. DocuSign-аккаунт живёт в аккаунте ПОЛЬЗОВАТЕЛЯ — Imperal не
может и не должен централизованно брокерить доступ к чужому DocuSign.

**WHY JWT GRANT, НЕ AUTHORIZATION CODE GRANT, И НЕ built-in `ext.oauth`.**

DocuSign не входит в built-in OAuth-провайдеров платформы (google/
microsoft/yahoo only, подтверждено в Docs/imperal-docs при Discovery
Salesforce Connector — тот же вывод переносится сюда). Из двух реальных
альтернатив (см. CONNECTOR_DISCOVERY.md §3) выбран JWT Grant, а не
Authorization Code Grant, по тем же причинам, по которым Salesforce
Connector выбрал Client Credentials Flow вместо delegated user OAuth:
service integration не требует browser redirect на каждого пользователя,
не нуждается в хранении refresh token (JWT Grant его вообще не выдаёт —
токен на 1 час перевыпускается заново на каждый вызов, требующий свежего
токена), и хорошо ложится в модель "подключил один раз — работает
автоматизированно". Плата за это — пользователь должен один раз вручную
дать consent через специальный URL (`account-d.docusign.com/oauth/auth?
response_type=code&scope=signature+impersonation&client_id=...` или
`account.docusign.com/...` для production) — коннектор строит эту ссылку
и отдаёт её пользователю как часть guided-connect потока, аналогично тому,
как GitLab CI/CD/n8n Connector объясняют, где взять токен, только здесь
шаг чуть сложнее (RSA keypair, DocuSign App генерируется в DocuSign Admin).

**WHY ХРАНИТСЯ RSA PRIVATE KEY, А НЕ ГОТОВЫЙ ТОКЕН.**

В отличие от CircleCI/GitLab CI/CD Personal API Token (готовый секрет,
вставляется один раз и живёт бессрочно), JWT Grant требует, чтобы сам
коннектор подписывал JWT заново каждый раз, когда нужен свежий access
token (токен живёт максимум 1 час). Поэтому в подключении хранится не
токен, а долгоживущие материалы для его генерации: Integration Key (client
ID), User ID (impersonated user GUID), RSA private key (PEM). Access token
кешируется в connection record с TTL и перевыпускается прозрачно при
истечении — тот же паттерн token-refresh, что у Salesforce/MuleSoft/Power
Automate Client Credentials коннекторов, только источник токена — не
client_secret, а подписанный JWT.

**WHY `base_uri` РЕЗОЛВИТСЯ ДИНАМИЧЕСКИ ПОСЛЕ ПЕРВОГО TOKEN EXCHANGE, А НЕ
ФИКСИРОВАН И НЕ ЗАДАЁТСЯ ПОЛЬЗОВАТЕЛЕМ ВРУЧНУЮ.**

DocuSign документированно возвращает пару `account_id`/`base_uri` через
`GET /oauth/userinfo` сразу после первого успешного token exchange —
`base_uri` зависит от датацентра аккаунта (например `na3.docusign.net`)
и НЕ равен домену auth-сервера. Коннектор вызывает `/oauth/userinfo` один
раз при подключении, сохраняет `account_id` + `base_uri` в connection
record, использует их на каждом последующем REST-вызове — не спрашивает
пользователя вручную (в отличие от GitLab CI/CD, где self-hosted URL
обязательно вводится пользователем, потому что там нет способа его
вывести программно).

**WHY ДВЕ СРЕДЫ (demo/production), А НЕ ОДНА.**

DocuSign официально разделяет sandbox (`account-d.docusign.com` /
`demo.docusign.net`) и production (`account.docusign.com` /
`www.docusign.com`) как физически разные системы с разными аккаунтами —
не query-параметр, а разный домен auth-сервера. Коннектор просит
пользователя выбрать среду при подключении (по умолчанию demo/sandbox для
безопасного первого теста, аналогично `sandbox_mode` у Stripe/Shopify
коннекторов), хранит выбор в connection record, используется для выбора
правильного auth-домена на каждом token refresh.

**WHY `write_mode="both"`**, та же логика, что все остальные BYOK-
коннекторы портфеля: `connect_docusign` даёт дружелюбный guided-путь с
объяснением JWT-консента, при этом generic Secrets screen остаётся как
fallback для продвинутых пользователей, уже имеющих готовые креды.

## 3. HTTP-клиент — общая механика

- Auth server: `account-d.docusign.com` (demo) / `account.docusign.com`
  (production) — `POST /oauth/token` с `grant_type=urn:ietf:params:oauth:
  grant-type:jwt-bearer` и подписанным JWT ассертом (RS256, приватный ключ
  пользователя).
- REST base: `https://{base_uri}/restapi/v2.1/accounts/{account_id}` —
  `base_uri`/`account_id` резолвятся один раз через `/oauth/userinfo` и
  кешируются в connection record (см. §2).
- Access token живёт максимум 1 час, кешируется с TTL-проверкой перед
  каждым REST-вызовом, перевыпускается прозрачно (`_ensure_token` helper,
  тот же паттерн, что token-refresh у Salesforce/MuleSoft Client
  Credentials клиентов).
- Ошибки: DocuSign возвращает `{"errorCode": "...", "message": "..."}` —
  прокидывается пользователю через `ClientFail` с этим `errorCode` как
  машиночитаемым идентификатором (аналогично тому, как CircleCI-клиент
  прокидывает `message` из JSON-ответа).
- Rate limit: DocuSign применяет burst + hourly limits per API group
  (Standard/Reporting) — поверхностно прокидывается через различение 429
  (rate limit) от 401/403 (auth), без специальной retry-логики сверх
  стандартного паттерна портфеля.

## 4. Ярусы функционала (полный список — см. CONNECTOR_DISCOVERY.md §4)

**Ярус 1 — ключевой цикл подписания (~20):**
connect_docusign, disconnect_docusign, list_connections,
create_envelope, get_envelope, list_envelopes, send_envelope_from_template,
void_envelope, resend_envelope, get_envelope_recipients,
update_envelope_recipients, get_envelope_documents,
get_envelope_document, get_envelope_tabs, update_envelope_tabs,
get_envelope_status_changes, list_templates, get_template,
create_template, get_recipient_view_url (embedded signing/sending URL).

**Ярус 2 — полнота eSignature-домена (~24):**
create_template_from_envelope, delete_template, get_template_documents,
get_template_recipients, update_template_recipients,
create_bulk_send_list, get_bulk_send_lists, create_bulk_send_request,
get_bulk_send_batch_status, list_folders, get_folder_envelopes,
move_envelopes_to_folder, list_powerforms, create_powerform,
get_powerform, delete_powerform, list_users, get_user, create_user,
update_user, deactivate_user, list_groups, create_group,
add_users_to_group, list_permission_profiles.

**Ярус 3 — брендинг + Connect webhooks + custom tabs + value-add (~20):**
list_brands, get_brand, create_brand, delete_brand, apply_brand_to_envelope,
create_connect_configuration, list_connect_configurations,
delete_connect_configuration, list_connect_failures, retry_connect_failure,
list_custom_tabs, create_custom_tab, delete_custom_tab,
get_envelope_audit_events, get_envelope_form_data, get_account_information,
get_bcc_email_archive_configuration, set_bcc_email_archive_configuration,
audit_account (value-add, тот же паттерн, что audit_org/audit_estate/
audit_cloudhub_environment), bulk_void_envelopes, bulk_resend_envelopes.

Итого ~64 chat-функции.

## 5. Деструктивные операции — требуют явного подтверждения

Per стандартной архитектуре портфеля (`action_type="destructive"`):
void_envelope, delete_template, delete_powerform, deactivate_user,
delete_brand, delete_connect_configuration, delete_custom_tab,
bulk_void_envelopes. `resend_envelope`/`bulk_resend_envelopes` помечены
как обычные write (не destructive) — повторная отправка не разрушает
состояние, в отличие от аннулирования конверта.

## 6. UI (panels.py / panels_settings.py) — per UI_INTERFACE_STANDARD.md

Левый сайдбар: список подключений + форма подключения (поля: Integration
Key с лейблом "Integration Key" и контекстным плейсхолдером вида
"a1b2c3d4-...", User ID с лейблом "User ID (impersonated user GUID)",
RSA Private Key с лейблом "RSA Private Key (PEM)" — многострочное поле,
Environment с лейблом "Environment" — выбор demo/production, по умолчанию
demo). Форма растянута на всю ширину сайдбара, содержимое — на всю ширину
формы, каждый Input с собственным видимым лейблом (никогда placeholder-
only), плейсхолдер всегда контекстно-специфичный. Никаких инструкций,
дублирующих модалку — кнопка "?" рядом с формой открывает модалку с
пошаговой инструкцией (создать DocuSign App в Admin, включить JWT Grant,
сгенерировать RSA keypair, дать consent через builder-ссылку), сайдбар
статических инструкций не содержит. Единственная secondary-кнопка "App
settings" — последний элемент сайдбара, ведёт в центр-слот с disconnect
per-connection.

## 7. Решение по объёму — уже принято пользователем

Задача #2263 прямо содержит "максимальная форма со всеми доступными
функциями" — трактуется как явное решение строить Ярус 1+2+3 без
дополнительного вопроса, по прецеденту CircleCI/GitLab CI/CD/Power
Automate/MuleSoft/UiPath/Blue Prism/Automation Anywhere/Cin7 Core/
ShipStation/PagerDuty.
