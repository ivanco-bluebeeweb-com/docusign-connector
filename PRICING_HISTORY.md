# Pricing History — DocuSign Connector

Обязательный журнал: каждое выставление или изменение цен на функции этого
приложения фиксируется здесь — что изменилось, почему, и на основании
чего. Не переписывать прошлые записи — только дописывать новые сверху.

---

## 2026-08-22 — первичный прайсинг (per_action, revenue_split_dev=95)

**Карта цен — фиксированная платформенная шкала {0, 8, 16, 20, 40, 60}**
построена по `action_type` + семантике имени для всех 55 функций манифеста
(зеркалирует `tool-prices.json`):

| Цена | Категория | Примеры |
|---|---|---|
| 0 | connect/disconnect/список подключений/consent URL | `connect_docusign`, `disconnect_docusign`, `list_connections`, `get_consent_url` |
| 8 | read (list/get) | `list_envelopes`, `get_envelope`, `list_templates`, `get_account_info` |
| 16 | write простой (create/update/delete одной сущности) | `create_template`, `create_group`, `update_recipients`, `delete_powerform` |
| 20 | write с реальным операционным эффектом (отправка/аннулирование конверта) | `create_envelope`, `send_bulk_envelope`, `void_envelope`, `resend_envelope`, `correct_envelope` |
| 40 | аудит/агрегированный отчёт | `audit_account_health` |
| 60 | массовые операции | `bulk_void_envelopes`, `bulk_resend_envelopes` |

**Процесс:** `update_pricing` прошёл без ошибки с первого вызова (в отличие
от большинства других приложений в этой сессии — известный транзиентный
баг платформы, задача #2275, здесь не проявился). `deploy_app` → 20/21
(commit 23c5ccd8). Последующий `submit_for_review` вернул `Cannot submit
app in status 'pending_review'` — приложение уже находилось в
`pending_review` до этого прайсинга (отправлено на ревью раньше в рамках
исходной разработки), поэтому дополнительная отправка не требовалась;
статус подтверждён неизменным — `pending_review`.
