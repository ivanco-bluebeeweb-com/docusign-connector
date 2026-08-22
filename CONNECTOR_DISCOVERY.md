# DocuSign Connector — Connector Discovery

**Дата discovery:** 2026-08-22
**Статус:** Ярусы 1-3 пройдены (чтение официальной документации
developers.docusign.com, 2026-08-22). Задача #2263 явно заявляла "максимальная
форма со всеми доступными функциями с их стороны и всеми возможными функциями
внутри нашего приложения" — трактуется как заранее заявленное решение объёма
("максимум"), тот же прецедент, что CircleCI/GitLab CI/CD/MuleSoft/Power
Automate/UiPath/Blue Prism/Automation Anywhere/Cin7 Core/ShipStation/PagerDuty
коннекторы: §7 (решение по объёму) не требует повторного вопроса Владу.

---

## 1. Целевой сервис и источники

DocuSign — рыночный лидер e-signature / agreement management. Прочитаны
2026-08-22:

- `developers.docusign.com/docs/esign-rest-api/reference/` — полный список
  категорий ресурсов eSignature REST API v2.1 (подтверждено рендерингом
  страницы: Envelopes, Templates, Bulk envelopes, PowerForms, Folders, Users,
  Groups, Brands, Connect, Custom tabs, Diagnostics/request logging, BCC email
  archive, Payments, eNotary (Legacy), Workspaces, Invoices, Account
  management, Cloud storage providers)
- `developers.docusign.com/platform/auth/jwt/` — JSON Web Token (JWT) Grant:
  service-integration flow, RSA keypair, impersonation конкретного
  пользователя аккаунта на длительной основе, **без refresh token**, токен
  живёт максимум 1 час
- `developers.docusign.com/platform/auth/authcode/` — Authorization Code
  Grant (Confidential/Public) — delegated user OAuth, требует redirect/consent
  UI на каждого конечного пользователя
- `github.com/docusign/OpenAPI-Specifications` — официальный Swagger/OpenAPI
  для eSignature REST API (структурный источник для полного списка операций)
- Отдельные продуктовые API у DocuSign (подтверждено наличие отдельных
  reference-разделов, НЕ входят в eSignature REST API v2.1): Rooms API,
  Click API, Admin API, Monitor API, Maestro API, Navigator API, Web Forms
  API — каждый со своим OAuth-скоупом и зачастую отдельным продуктовым
  аккаунтом/лицензией у DocuSign.

## 2. КРИТИЧНО: DocuSign — это СЕМЕЙСТВО API, не один API. Сознательный выбор
eSignature REST API v2.1 как ядра.

DocuSign продаёт несколько отдельных продуктов, каждый со своим API:

- **eSignature REST API v2.1** (`developers.docusign.com/docs/esign-rest-api`)
  — базовый, самый зрелый, самый широко используемый продукт: отправка
  конвертов (envelopes) на подпись, шаблоны, получатели, поля (tabs), массовая
  рассылка, PowerForms (самообслуживаемые формы), папки, управление
  пользователями/группами/брендами аккаунта, Connect webhooks, кастомные поля,
  диагностика запросов, BCC-архивация, платежи внутри конверта (payment tabs),
  eNotary (legacy notarization), Workspaces (устаревший коллаборационный
  модуль), инвойсы биллинга DocuSign. **Это единственная поверхность, которую
  покрывает данный коннектор** — как единственный продукт, доступный
  практически любому платному DocuSign-аккаунту без отдельной лицензии.
- **Rooms API** — real estate transaction rooms, требует отдельный продукт
  DocuSign Rooms (не входит в стандартный eSignature план) — сознательно вне
  охвата, как MuleSoft Metadata/Tooling/Streaming API были вне охвата у
  Salesforce Connector.
- **Click API** — clickwrap "I agree" виджеты, отдельный продукт DocuSign
  Click — вне охвата.
- **Admin API** — организационное управление на уровне DocuSign Organization
  (не Account) — управление несколькими аккаунтами сразу, обычно доступно
  только Enterprise Org Admin — вне охвата.
- **Monitor API** — событийный лог для compliance/SIEM-интеграций, отдельный
  продукт Monitor — вне охвата.
- **Maestro API** — no-code оркестрация workflow поверх eSignature, отдельный
  бета/GA продукт — вне охвата.
- **Navigator API** — AI-агрегация метаданных подписанных договоров, отдельный
  продукт Navigator — вне охвата.
- **Web Forms API** — расширенная альтернатива PowerForms с адаптивным UI,
  отдельный продукт — вне охвата.

Это решение объёма, аналогичное прошлым Discovery (Salesforce: только REST/
Bulk/Composite/SOQL/SOSL, без Metadata/Tooling/Streaming API — те требуют
отдельных SOAP/Bayeux клиентов). eSignature REST API v2.1 в одиночку —
крупнейшая по числу операций поверхность в этом семействе и покрывает 100%
сценария "отправить документ на подпись, отследить статус, управлять
шаблонами/пользователями/аккаунтом" — то есть именно то, что подавляющее
большинство клиентов подразумевает под словом "DocuSign".

## 3. Авторизация — JWT Grant (service integration), НЕ Authorization Code Grant

DocuSign документирует два практических варианта OAuth 2.0 для интеграций:

- **JWT Grant** — RSA keypair, зарегистрированный в Integration Key
  (DocuSign App) на developers.docusign.com. Сервисная интеграция
  импersonates (действует от имени) заранее выбранного пользователя аккаунта
  на постоянной основе, без необходимости его присутствия при каждом запросе.
  Явно рекомендован DocuSign для "system/admin login"-сценариев и управления
  большим числом пользователей через Docusign Admin — то есть именно
  server-to-server автоматизация, которую строит Imperal. **Не выдаёт refresh
  token** — токен короткоживущий (до 1 часа), клиент обязан минтить новый JWT
  и обменивать его на access token заново при истечении (или заранее, по
  таймеру) — паттерн, аналогичный Salesforce Client Credentials Flow (тоже
  без refresh token, тоже короткоживущий токен, тоже перечеканка на каждый
  холодный вызов).
- **Authorization Code Grant** (Confidential/Public) — классический delegated
  user OAuth c redirect/consent на КАЖДОГО конечного пользователя. Не подходит
  для BYOK-модели "один коннектор одного аккаунта Imperal-пользователя",
  поскольку требует держать браузерный redirect UI и refresh token ротацию
  под каждого end-user отдельно — избыточная сложность для сценария "я
  подключаю СВОЙ собственный DocuSign-аккаунт".

**Выбор: JWT Grant**, тот же архитектурный паттерн, что Salesforce Connector
(BYOK Connected App, без ext.oauth редиректа, единый набор полей на подключение,
`write_mode="both"` — все создающие/изменяющие функции пишут напрямую в
DocuSign через REST, ничего не проксируется/не кэшируется помимо самого
короткоживущего access token).

**Поля подключения (собираются от пользователя один раз при `connect_docusign`):**
- `integration_key` (Client ID / App Integration Key, из DocuSign Admin →
  Apps and Keys)
- `user_id` (GUID пользователя аккаунта, от имени которого действует
  интеграция — impersonated user, из My Account Info в DocuSign Admin)
- `account_id` (GUID DocuSign-аккаунта — API Account ID, из My Account Info)
- `private_key` (RSA-приватный ключ в формате PEM, сгенерированный при
  создании Integration Key в паре с публичным ключом, загруженным в DocuSign)
- `is_demo` (bool: аккаунт в DocuSign Developer/Demo окружении
  `account-d.docusign.com` vs Production `account.docusign.com` — критично
  для правильного auth-сервера и base URI; DocuSign прямо предупреждает не
  путать демо- и прод-окружения, у них разные ключи и разные consent)

**Consent:** JWT Grant для НОВОГО Integration Key требует одноразового
получения consent (согласия) пользователя через `/oauth/auth?...&response_
type=code&scope=signature%20impersonation` — сохранена ссылка-помощник
(`build_consent_url`) в connection handlers, чтобы пользователь мог один раз
открыть её в браузере и подтвердить согласие ДО первого JWT-обмена (тот же
паттерн, что Google/Microsoft consent screens у других коннекторов, но здесь
это ручная ссылка, а не built-in ext.oauth redirect, потому что DocuSign не
входит в платформенный список built-in OAuth провайдеров).

## 4. Полный охват операций eSignature REST API v2.1 (Ярусы 1+2+3)

### Ярус 1 — ядро (envelopes/templates/recipients/status)
- Создание и отправка конверта (`POST /envelopes`) — с документами (base64),
  получателями (signers/carbonCopies/certifiedDeliveries/inPersonSigners),
  вкладками (tabs: sign here, date signed, text, checkbox, radio, list,
  initial here), email-настройками, статусом draft/sent
- Получение конверта, списка конвертов (с фильтрами по статусу/дате), статуса
- Void (отзыв) конверта, resend (повторная отправка уведомления), correct
  (исправление ошибочно отправленного конверта до подписания)
- Список документов конверта, получение конкретного документа/комбинированного
  PDF, список получателей конверта (с их статусами подписания), обновление
  получателей (например смена email до подписания), список вкладок получателя
- Список аудиторских событий конверта (audit trail), сертификат завершения
  (Certificate of Completion)
- Создание/управление шаблонами (create/list/get/delete template), список
  документов шаблона, список получателей-заполнителей шаблона (roles)
- Отправка конверта ИЗ шаблона (`compositeTemplates`)

### Ярус 2 — расширенное управление
- Массовая рассылка (Bulk Send): создание bulk-списка получателей, отправка
  конверта массово по списку, статус bulk-рассылки
- PowerForms: создание/список/получение самообслуживаемых форм подписания
- Папки (Folders): список папок, содержимое папки, перемещение конверта между
  папками
- Пользователи аккаунта: список/создание/получение/обновление пользователей,
  список групп, создание группы, добавление пользователей в группу
- Бренды (Brands): список/получение брендов оформления писем/страниц подписания
- Кастомные поля аккаунта (Custom Fields): список, создание (используются для
  тегирования и поиска конвертов)
- Connect (webhooks): список конфигураций Connect, создание конфигурации
  (подписка на события envelope-completed/sent/declined/voided и т.д.), список
  событий/неудачных доставок, ретрай неудачной доставки, удаление конфигурации
- BCC Email Archive: список/добавление BCC-адресов для архивации исходящих
  писем DocuSign

### Ярус 3 — диагностика, платежи, аккаунт, аудит
- Diagnostics / Request logging: включение логирования запросов на аккаунте,
  список логов, получение/удаление конкретного лога
- Payments: список payment gateway-аккаунтов, подключённых к DocuSign-аккаунту
  (для payment tabs внутри конвертов)
- Account management: получение информации об аккаунте, лимитов/настроек,
  списка billing-инвойсов (Invoices resource)
- Cloud storage providers: список подключённых облачных хранилищ на аккаунте
- **Value-add отчёты (по прецеденту всех предыдущих коннекторов):**
  `audit_account` — агрегированный health-снапшот: доля конвертов voided/
  declined за период, самые "зависшие" (sent, но не completed >N дней)
  конверты, список активных Connect-подписок с недавними сбоями доставки;
  `bulk_void_envelopes` / `bulk_resend_envelopes` — те же bulk-удобства, что у
  MuleSoft/CircleCI/GitLab CI/CD (`bulk_*` обёртки по явным id, продолжают
  выполнение после ошибки одного элемента, репортят per-item результат)

### Сознательно вне охвата этого коннектора
- eNotary (Legacy) — DocuSign сам маркирует его Legacy, заменён отдельным
  Notary продуктом вне eSignature REST API v2.1
- Workspaces — устаревший коллаборационный модуль, DocuSign рекомендует Rooms
  вместо него (которого тоже нет в охвате — см. §2)
- Rooms/Click/Admin/Monitor/Maestro/Navigator/Web Forms API — отдельные
  продукты, см. §2

## 5. Архитектурные решения (по прецеденту портфеля)

- **BYOK**, `write_mode="both"` — аналогично Salesforce/MuleSoft/Stripe/
  CircleCI. DocuSign-аккаунт целиком принадлежит пользователю.
- **JWT Grant с ручным consent-URL помощником**, без built-in `ext.oauth`
  (DocuSign не входит в built-in провайдеры платформы: google/microsoft/
  yahoo only) — см. §3.
- **base_uri выбирается динамически** после первого успешного token exchange:
  DocuSign возвращает `account_id`→`base_uri` пару через `/oauth/userinfo`
  (например `https://na3.docusign.net/restapi`) — это ОБЯЗАТЕЛЬНЫЙ шаг перед
  любым REST-вызовом, DocuSign явно документирует, что base_uri аккаунта
  может отличаться по датацентру и НЕ равен домену auth-сервера
  (`account-d.docusign.com`/`account.docusign.com`) — сохраняется в
  connection record при первом подключении, не захардкожен.
- **Фиксированная платформенная шкала цен {0, 8, 16, 20, 40, 60}** —
  применяется по `PRICING_POLICY.md`, выставляется ДО `submit_for_review`, в
  той же сессии, что и `deploy_app` (обязательное правило после инцидента
  MuleSoft Connector).
