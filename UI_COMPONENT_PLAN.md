# DocuSign Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на `POST_CONNECT_EXPERIENCE.md` этого приложения.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(account) + `ui.Divider` + navigation `ui.ListItem`(Envelopes/Templates/PowerForms) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Envelope List (center, `center_overlay=True`) | `ui.Stats`(Sent/Completed/Voided this month) + `ui.Select`(param_name="status_filter") + `ui.DataTable`(subject, recipients count, status Badge sent/delivered/completed/voided, sent date; sortable) | `DataTable` — стандартный способ работы с потоком конвертов на подпись. |
| Envelope Detail | Back-button + `ui.KeyValue`(subject/sender/sent date) + `ui.Timeline`(recipient statuses: sent→viewed→signed, по каждому получателю) + `ui.Row`(Button "Resend", "Void", "Correct") | `Timeline` точно отражает последовательность подписания разными получателями. |
| Void Dialog | `ui.Dialog`(title="Аннулировать конверт?", content=`ui.TextArea`(param_name="void_reason", placeholder="Причина аннулирования..."), confirm_label="Аннулировать") | Аннулирование — необратимое действие, обязателен `Dialog` с явным подтверждением. |
| Template List | `ui.List`(templates: name, roles count) + `ui.Button`("Создать конверт из шаблона") | Простой список шаблонов для быстрого запуска подписания. |
| Create Envelope Form | `ui.Form`(action="create_envelope_from_template") + `ui.Select`(template_id) + N×`ui.Row`([`ui.Input`(type="email", recipient_email), `ui.Input`(recipient_name)]) генерируется по числу ролей шаблона + `ui.Button`("Отправить на подпись") | Количество получателей определяется выбранным шаблоном — форма подстраивается серверным re-render после выбора Select. |
| PowerForm List | `ui.DataTable`(name, url, status active/inactive) | Публичные self-service ссылки для подписания без создания конверта вручную. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Brands, Webhooks CRUD]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__docusign_sidebar` рендерит account + разделы;
   `auto_action` открывает Envelope List, если `not active_view`.
2. Envelope List: Select фильтра статуса → DataTable → клик на строку →
   `ui.Call("__panel__docusign_center", envelope_id=...)` → Envelope Detail.
3. Envelope Detail: Button "Void" → `ui.Dialog` подтверждения с TextArea причины →
   `void_envelope` → `refresh_panels=["docusign_center"]`.
4. Раздел "Templates" → List шаблонов → клик "Создать конверт из шаблона" →
   Create Envelope Form (Select шаблона меняет число строк получателей через
   `on_change` → `ui.Call` перерисовывает форму) → Button "Отправить" →
   `create_envelope_from_template` → возврат к Envelope List с новым конвертом сверху.
5. "App settings" → отдельный center overlay с Accordion-секциями.

## 3. Конкретные экраны (screens)

### Screen: Envelope List (`docusign_center`, default)
- Stats row: Sent / Completed / Voided this month.
- Select (статус) сверху таблицы.
- DataTable: subject, recipients, status Badge, sent date — row-click → Envelope Detail.

### Screen: Envelope Detail (`docusign_center` + `envelope_id`)
- Back-button "← К конвертам".
- KeyValue: subject, sender, sent date.
- Timeline: статус каждого получателя (sent→viewed→signed).
- Row кнопок: Resend, Void (открывает Dialog), Correct.

### Screen: Create Envelope (`docusign_create` + `template_id`)
- Select шаблона.
- Динамический блок Row-пар Input(email)+Input(name) — по числу ролей шаблона.
- Button "Отправить на подпись".

### Screen: App settings (`docusign_settings`)
- Accordion "Подключение": account info, Disconnect (Dialog-подтверждение).
- Accordion "Бренды": List визуальных брендов.
- Accordion "Webhooks": List + Button "Добавить".
