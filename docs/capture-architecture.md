# Fincorder Capture System and Data Model

This document describes the implemented capture system as it exists in the backend. It covers the conversational capture flow, review mode, automatic mode, clarification state, updates, archival, tool calling, deterministic safeguards, and every database model used by capture.

The capture system is transaction-only. It does not calculate or maintain account balances. Accounts are references that identify where a transaction happened; the current capture workflow does not store an account-level balance.

## 1. The central design

The system has three responsibilities:

1. The language model interprets the user's natural language.
2. Deterministic backend code preserves explicit user facts and validates the model's result.
3. The transaction service performs the database mutation only after the result passes validation.

The model never receives direct database access. It returns a structured action through the provider layer. The backend resolves names to IDs, checks ownership, checks transaction rules, and then either stores a proposal or applies the action.

The high-level flow is:

```text
HTTP request
  -> authenticate user
  -> lock user capture state
  -> check retry receipt
  -> load conversation, messages, drafts and recent transactions
  -> ask the AI provider for a structured action
  -> select or create a financial event
  -> merge known facts and apply safe defaults
  -> validate the complete action batch
  -> review mode: save an awaiting-confirmation proposal
     automatic mode: apply the validated batch
  -> save assistant message and event state
  -> commit everything in one database transaction
```

The main implementation files are:

| File | Responsibility |
| --- | --- |
| `app/modules/capture/controller.py` | HTTP endpoints and error mapping |
| `app/modules/capture/service.py` | Capture orchestration and event lifecycle |
| `app/modules/capture/context_builder.py` | Builds model context from database state |
| `app/modules/capture/state.py` | Draft merging, explicit-fact preservation, and defaults |
| `app/modules/capture/execution.py` | Validation and transaction application |
| `app/modules/capture/helpers.py` | Small deterministic parsers and entity resolution |
| `app/ai/openai_provider.py` | OpenAI Responses API tool-calling loop |
| `app/ai/provider.py` | Provider interface and context formatting |
| `app/ai/schemas.py` | Structured AI action schema |
| `app/ai/prompts.py` | Extraction and continuity rules |

## 2. Capture modes

The `users.review_transactions` column controls the normal capture mode for a user.

| `review_transactions` | Behavior |
| --- | --- |
| `true` | The AI returns a transaction proposal. The user must review and confirm it. This is the default. |
| `false` | A complete, valid action is applied automatically. Incomplete or invalid actions remain in clarification and are not partially applied. |

The preference is returned by register, login, refresh, and `/auth/me`. It can be changed through `PATCH /auth/me`.

Changing the preference does not automatically apply proposals that were already waiting for confirmation. Those proposals remain explicit review items.

An existing awaiting-confirmation proposal is always treated as a review item, even if the user later turns automatic mode on. This prevents an old proposal from being silently applied because a setting changed after it was created.

## 3. Database model overview

Capture does not write directly to a single `transactions` row. The durable structure is:

```text
User
  ├── Conversations
  │     ├── Messages
  │     └── FinancialEvents
  │            └── TransactionGroups
  │                   └── Transactions
  ├── Accounts
  ├── Categories
  ├── People
  └── CaptureReceipts
```

The important relationship is:

```text
FinancialEvent -> TransactionGroup -> Transaction
```

The group is created when a new transaction is actually applied. A review proposal by itself does not create a transaction group or transaction rows.

Updates and archives target existing transactions. They do not create a new transaction group unless the same action batch also contains new transactions.

## 4. `users` table

Model: `app/modules/users/models.py`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Primary key. |
| `name` | string | no | User display name. |
| `review_transactions` | boolean | no | Capture mode. Defaults to `true`. |
| `timezone` | string(64) | no | IANA timezone used for date defaults. Defaults to `UTC`. |
| `status` | enum | no | `active`, `suspended`, or `deleted`. |
| `created_at` | timezone datetime | no | Account creation time. |
| `updated_at` | timezone datetime | no | Last profile update time. |

Capture uses `review_transactions` and `timezone` directly. The user's timezone is used when the message does not include a date. For example, a message sent around midnight is assigned its date in the user's configured timezone rather than blindly using the server's date.

## 5. `accounts` table

Model: `app/modules/accounts/models.py`

Accounts describe where a transaction occurred. They are not balance accounts in the capture implementation.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Primary key. |
| `user_id` | UUID | no | Owner. References `users.id`; cascade delete. |
| `name` | string(100) | no | User-facing name such as `Cash` or `Spending Account`. |
| `currency` | string(3) | no | Default currency associated with the account. |
| `is_active` | boolean | no | Whether the account is active. |
| `is_default` | boolean | no | Whether capture should use it when no account is mentioned. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last update time. |
| `deleted_at` | timezone datetime | yes | Soft-delete timestamp. |

The default-account migration added `is_default`. The account service keeps one selected default account per user. If no explicit account is supplied, capture uses the selected default, then `Spending Account`, then the first available account as a final fallback.

## 6. `categories` table

Model: `app/modules/categories/models.py`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Primary key. |
| `user_id` | UUID | no | Owner. References `users.id`; cascade delete. |
| `name` | string(100) | no | Category name. |
| `type` | enum | no | `expense` or `income`. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last update time. |
| `deleted_at` | timezone datetime | yes | Soft-delete timestamp. |

Categories are supplied to the model as names. The backend resolves the returned name to the current user's category ID. An unknown category is rejected instead of being silently mapped to another category.

## 7. `people` table

Model: `app/modules/people/models.py`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Primary key. |
| `user_id` | UUID | no | Owner. References `users.id`; cascade delete. |
| `name` | string(100) | no | Person name used in conversational resolution. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last update time. |
| `deleted_at` | timezone datetime | yes | Soft-delete timestamp. |

`person_id` is required by backend validation for `lend`, `borrow`, and `repayment` transactions. This prevents a lending message from becoming an ordinary expense without a person attached.

## 8. `conversations` table

Model: `app/modules/conversations/models.py`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Conversation primary key. |
| `user_id` | UUID | no | Owner. References `users.id`; cascade delete. |
| `title` | string(255) | yes | Sidebar title. Automatically suggested from the first message and user-editable. |
| `status` | enum | no | `active` or `archived`. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last activity time. |

Archived conversations are hidden from the active conversation list. Their messages and financial events remain in the database.

## 9. `messages` table

Model: `app/modules/messages/models.py`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Message primary key. |
| `conversation_id` | UUID | no | Parent conversation; cascade delete. |
| `role` | enum | no | `user`, `assistant`, or `system`. |
| `content` | text | no | Original message text. Newlines are preserved. |
| `created_at` | timezone datetime | no | Message creation time. |

Capture creates a user message before calling the provider and an assistant message after the result has been processed. The assistant message is linked back to the financial event through `financial_events.assistant_message_id`.

The model context uses the latest conversation messages, excluding the message currently being processed. The current implementation sends up to the previous ten messages, ordered chronologically.

## 10. `financial_events` table

Model: `app/modules/financial_events/models.py`

This is the durable capture state machine. It represents the user's requested financial action, whether or not it has become a transaction.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Financial-event primary key. |
| `conversation_id` | UUID | no | Parent conversation; cascade delete. |
| `source_message_id` | UUID | no | Original user message that started the event. |
| `assistant_message_id` | UUID | yes | Assistant message that explains the current event result or proposal. Uses `SET NULL` on message deletion. |
| `status` | enum | no | Event state. |
| `raw_text` | text | no | Original capture message. |
| `revision` | integer | no | Draft revision used for optimistic concurrency checks. Starts at `1`. |
| `extracted_data` | JSONB | yes | Structured AI response, saved draft transactions, validation data, result IDs, and audit information. |
| `missing_fields` | JSONB array | yes | Fields still required before the event can be completed. |
| `error` | text | yes | Provider or processing error. |
| `created_at` | timezone datetime | no | Event creation time. |
| `updated_at` | timezone datetime | no | Last event update time. |

### Event statuses

The API exposes lowercase values even though PostgreSQL stores the SQLAlchemy enum values internally.

| Status | Meaning |
| --- | --- |
| `pending` | Event created but not yet processed. |
| `processing` | Reserved processing state. |
| `needs_clarification` | More information is required. No transaction has been written. |
| `awaiting_confirmation` | Complete proposal is saved and waiting for review confirmation. |
| `completed` | Automatic execution or user confirmation finished successfully. |
| `rejected` | User rejected the proposal. The event and proposal data remain stored. |
| `failed` | Processing failed and could not produce a usable action. |

The older implementation used `needs_clarification` for completed proposals waiting for review. The current migration adds `awaiting_confirmation` so clarification and confirmation have separate states.

### `extracted_data` structure

`extracted_data` is intentionally JSONB because it stores the evolving conversational draft and execution audit. A typical review event contains data similar to:

```json
{
  "status": "completed",
  "mode": "review",
  "transactions": [
    {
      "draft_id": "draft-identifier",
      "operation": "create",
      "transaction_id": null,
      "type": "expense",
      "amount": 500,
      "currency": "INR",
      "account": "Spending Account",
      "category": "Transport",
      "person": null,
      "description": "Petrol",
      "transaction_date": "2026-09-23",
      "direction": "debit",
      "clear_fields": []
    }
  ],
  "target_versions": {},
  "validation_error": null
}
```

An automatically completed event additionally stores `transaction_ids`, `before`, and `result_message`. For updates and archives, `before` stores the previous values needed for audit visibility.

## 11. `transaction_groups` table

Model: `app/modules/transaction_groups/models.py`

Transaction groups represent one applied financial event and allow related rows, especially transfer pairs, to be committed together.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Group primary key. |
| `financial_event_id` | UUID | no | Parent event; cascade delete. |
| `status` | enum | no | `pending`, `posted`, or `reversed`. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last update time. |

For a new transaction batch, the executor creates one group, creates all transaction rows under that group, and marks the group `posted` before committing. A transfer normally has two rows in the same group: one debit and one credit.

## 12. `transactions` table

Model: `app/modules/transactions/models.py`

This is the final financial record used by the transaction history and future reports.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `id` | UUID | no | Transaction primary key. |
| `transaction_group_id` | UUID | no | Parent applied group; cascade delete. |
| `user_id` | UUID | no | Owner; cascade delete. |
| `account_id` | UUID | no | Account reference. |
| `category_id` | UUID | yes | Category reference. |
| `person_id` | UUID | yes | Person reference. Required by validation for lending, borrowing, and repayment. |
| `type` | enum | no | `expense`, `income`, `transfer`, `lend`, `borrow`, or `repayment`. |
| `direction` | enum | no | `debit` or `credit`. |
| `amount` | numeric(12,2) | no | Positive monetary amount. |
| `currency` | string(3) | no | Three-letter currency code. |
| `description` | text | yes | Human-readable purpose. |
| `transaction_date` | timezone datetime | no | Date/time the transaction happened. |
| `created_at` | timezone datetime | no | Creation time. |
| `updated_at` | timezone datetime | no | Last update time. Used for stale-proposal checks. |
| `deleted_at` | timezone datetime | yes | Soft-archive timestamp. |

The transaction list repository filters `deleted_at IS NULL`, so an archived row disappears from active history while remaining available in the database.

## 13. `capture_receipts` table

Model: `app/modules/capture/models.py`

This table makes capture requests idempotent when the frontend retries after a timeout or lost response.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `user_id` | UUID | no | Part of the composite primary key and ownership boundary. |
| `request_id` | UUID | no | Client-generated request identifier. Part of the composite primary key. |
| `fingerprint` | text | no | Hash of the message and target context. |
| `response` | JSONB | no | Previously returned `CaptureResponse`. |

If the same user sends the same `request_id` again with the same fingerprint, the saved response is returned and the AI is not called again. Reusing the request ID for a different message is rejected.

## 14. AI input and output models

Models: `app/ai/schemas.py`

### `AITransaction`

Each item represents one proposed or executable operation.

| Field | Type | Meaning |
| --- | --- | --- |
| `draft_id` | string or null | Stable identity while a multi-turn draft is being merged. |
| `changed_fields` | string array | Fields the model believes the user explicitly changed during this turn. |
| `operation` | enum | `create`, `update`, or `delete`. |
| `transaction_id` | UUID or null | Existing transaction target for update/delete. Never invented by the model. |
| `type` | enum or null | Financial type. |
| `amount` | decimal or null | Monetary amount. The schema advertises a JSON number for GPT-4.1 but validates as `Decimal`. |
| `currency` | string or null | Currency code. Defaults are filled by backend logic. |
| `account` | string or null | Account name before backend ID resolution. |
| `category` | string or null | Category name before ID resolution. |
| `person` | string or null | Person name before ID resolution. |
| `description` | string or null | Transaction purpose. |
| `transaction_date` | string or null | ISO date/time text. |
| `clear_fields` | string array | Explicitly clearable fields: `category`, `person`, `description`. |
| `direction` | enum or null | `debit` or `credit`. |

### `CaptureAIResponse`

| Field | Type | Meaning |
| --- | --- | --- |
| `continuation_event_id` | UUID or null | Event selected when the user is continuing one of several drafts. |
| `status` | enum | `completed`, `needs_clarification`, or `failed`. |
| `transactions` | `AITransaction[]` | One or more action drafts. |
| `missing_fields` | string array | Fields the model still needs. |
| `assistant_message` | string | Model-generated explanation or question. |
| `confidence` | decimal between 0 and 1 | Model confidence metadata. The backend does not use this as permission to write. |

## 15. HTTP schemas and endpoints

### `POST /capture`

Request:

```json
{
  "message": "Spent 500 on petrol",
  "conversation_id": "optional-conversation-uuid",
  "request_id": "client-generated-uuid",
  "financial_event_id": "optional-draft-uuid"
}
```

`financial_event_id` explicitly selects the draft being continued. The frontend sends it when the user presses Resume on a particular draft.

Response fields:

| Field | Meaning |
| --- | --- |
| `conversation_id` | Conversation containing the capture. |
| `message_id` | Newly stored user message. |
| `assistant_message_id` | Newly stored assistant message. |
| `financial_event_id` | Event created or continued. |
| `status` | Current event status. |
| `assistant_message` | Text displayed in chat. |
| `needs_clarification` | Whether more information is required. |
| `missing_fields` | Missing field names. |
| `awaiting_confirmation` | Whether a review card should be shown. |
| `proposed_transactions` | Current draft array. |
| `transaction_ids` | IDs written during automatic execution. |
| `revision` | Current event revision. |

### `POST /capture/{financial_event_id}/confirm`

Used by review mode. The client submits the edited transaction array and the revision it displayed. The backend verifies the event state, revision, operation scope, target IDs, entity ownership, and target transaction versions before writing.

### `PATCH /capture/{financial_event_id}/draft`

Saves edits to an awaiting-confirmation proposal for later. It increments the event revision but does not create or update transactions.

### `POST /capture/{financial_event_id}/reject`

Marks a pending clarification or proposal as `rejected`. It does not delete the event, messages, or draft data.

### `GET /financial-events/conversation/{conversation_id}`

Returns all events for restoring chat history. The frontend uses `assistant_message_id` to attach a proposal to the correct assistant message. It does not infer the relationship from assistant text or array position.

## 16. OpenAI tool-calling flow

When capture has a context object, the OpenAI provider uses the Responses API tool loop.

The action tool is selected from the user preference:

```text
review_transactions = true   -> propose_transactions
review_transactions = false  -> apply_transactions
```

The action tool uses the `CaptureAIResponse` schema. The model must return one structured batch containing either completed transactions or a clarification response.

The provider also exposes one read-only tool:

```text
search_transactions(search, date_from, date_to)
```

The search tool is limited to the current authenticated user's transactions. It returns a small list of matching records with IDs, amounts, dates, descriptions, accounts, categories, and people. It exists mainly for updates and archives so the model can identify an exact old transaction.

The loop has these constraints:

- Tool choice is required.
- Parallel tool calls are disabled.
- The loop is capped at four model calls.
- The provider does not expose arbitrary SQL or write tools to the model.
- Search results are treated as data, not instructions.
- The final action still passes through backend validation.

The current Gemini provider remains compatible with the same structured response and backend executor, but the OpenAI provider is the active tool-calling implementation used with the configured OpenAI mode.

## 17. Context sent to the model

The context builder supplies:

```text
today
timezone
accounts
account_details and currencies
default_account
categories
people
recent transactions, up to 20
previous conversation messages, up to 10
pending draft events
review_transactions
selected_event_id, when the user explicitly resumed a draft
```

A recent transaction contains its ID, group ID, direction, type, amount, currency, account name, category name, person name, description, and transaction date.

This context lets the model distinguish:

- A new transaction from an update.
- One old transaction from another transaction with the same amount.
- A debit transfer entry from a credit transfer entry.
- A reply to a pending lending draft from a new expense.

The backend still keeps the stored event facts authoritative during merging. The model's new response cannot casually replace a previously known amount or target ID.

## 18. Clarification and draft merging

When a response is incomplete, the event stores the current draft in `extracted_data.transactions` and sets `missing_fields`.

On the next message:

1. The model can explicitly return `continuation_event_id`.
2. The user can explicitly send `financial_event_id` through the Resume UI.
3. The OpenAI path uses those IDs to select the draft.
4. The compatibility path can continue the only clarification draft when the message does not look like a new transaction.
5. If several drafts exist and the message cannot identify one, the assistant asks the user to select a draft.
6. `draft_id` matches each returned transaction to the stored transaction draft.
7. Previously known values are retained unless the current answer fills a missing field or explicitly marks a field as changed.

For a simple example:

```text
User:      Spent 219
Event:     amount=219, type=expense, direction=debit, date=today, account=default
Assistant: What was the ₹219 for?

User:      Airtel recharge
Event:     amount=219, description/category updated, account still preserved
Assistant: Which account did you use?

User:      Cash
Event:     amount=219, description/category preserved, account=Cash
```

The event is not completed until the required fields are present and validation succeeds.

## 19. Deterministic backend logic and regular expressions

The regular expressions are narrow guardrails. They are not the main natural-language parser.

### Explicit amount extraction

`extract_explicit_amount` recognizes forms such as:

```text
₹219
219 rs
500 INR
Spent 1.2k
Paid 2 lakh
```

It is used to preserve an amount that the user explicitly typed. If the model returns a different amount for the same single transaction, the explicit user amount wins.

### Correction target extraction

`extract_correction_target_amount` recognizes the old amount in phrases such as:

```text
Not 500, I spent 219
Instead of 500, it was 219
Rather than 500, use 219
```

The backend then searches for a matching owned transaction. It updates only when there is an unambiguous target.

### New-message heuristic

`starts_new_transaction` is a small compatibility fallback. It recognizes action words such as `spent`, `paid`, `bought`, `lent`, `borrowed`, `received`, and `transferred`. It prevents a clarification answer from being mistaken for a new capture when a non-tool provider has one pending draft.

The OpenAI tool path has explicit draft IDs and does not rely on this heuristic when selecting among multiple drafts.

### Partial inference

`infer_partial_transaction` creates a minimal draft when the user has supplied an amount but the provider returns no transaction object. It infers only a broad type/direction, such as expense/debit for `Spent 200`, then leaves the missing semantic information for clarification.

### Entity resolution

Account, category, and person names are resolved with case-insensitive exact matching against the current user's records. The regex helpers do not decide which category or person the user meant.

### Validation-error field mapping

`validation_missing_field` converts an error such as “Transaction 2: choose a person” into a field marker such as `1.person`, allowing the next draft response to update the correct item in a batch.

## 20. Backend validation before writes

The shared executor in `execution.py` validates every operation before applying any operation in the batch.

It checks:

- The batch contains between 1 and 30 operations.
- Update/delete IDs belong to the authenticated user.
- Target transactions are not already archived.
- New transactions do not pretend to target an existing transaction.
- Accounts, categories, and people belong to the authenticated user.
- Amounts are positive, finite, and have at most two decimal places.
- Amounts fit the database precision limit.
- Currency is a three-letter alphabetic code.
- Expense and lending use debit.
- Income and borrowing use credit.
- Lending, borrowing, and repayment have a person.
- Expenses and income have a description or category.
- New transactions have a date.
- Transfer entries have matching amount/currency and opposite directions.
- Transfer entries use different accounts.
- Existing transfer changes do not leave an invalid unmatched pair.
- Stale transaction versions are rejected.

Validation happens before the write loop. Therefore an invalid second item cannot leave the first item committed.

## 21. Review confirmation protection

The client is allowed to edit proposal fields, but it cannot change the proposal's operation or target through confirmation.

For example, if the original event contains:

```json
{
  "operation": "update",
  "transaction_id": "existing-id"
}
```

The client cannot replace it with:

```json
{
  "operation": "delete",
  "transaction_id": "different-id"
}
```

The backend also checks the event `revision` and each target transaction's `updated_at` value. If another screen edited the transaction after the proposal was generated, confirmation is rejected and the user must obtain a fresh proposal.

The user row is locked during capture, confirmation, draft saving, and rejection. This serializes concurrent actions from multiple tabs for the same user.

## 22. Create, update, and archive behavior

### Create

For a create operation, the backend resolves entity names to IDs, creates a transaction group tied to the financial event, creates the transaction row, marks the group posted, and commits the event and messages together.

### Update

For an update operation, the backend loads the existing owned transaction and applies only fields present in the action. `clear_fields` explicitly removes category, person, or description. The previous values are stored in the event audit data.

### Archive

For a delete operation, the backend calls the existing soft-delete transaction service. It sets `deleted_at` and does not physically remove the row. The event stores the archived transaction ID and previous values.

## 23. Typical scenarios

### Complete transaction in review mode

```text
POST /capture
  -> awaiting_confirmation
  -> financial event stores proposal
  -> frontend displays editable card

POST /capture/{event_id}/confirm
  -> validate revision and target scope
  -> create group and transaction
  -> completed
```

### Complete transaction in automatic mode

```text
POST /capture
  -> model returns apply_transactions action
  -> backend validates
  -> transaction is created
  -> completed with transaction_ids
```

### Incomplete transaction

```text
User: Spent 200
  -> needs_clarification
  -> event stores amount=200 and missing_fields

User: Coffee
  -> same event is selected
  -> known amount is retained
  -> event either asks for the next field or completes
```

### Correction

```text
User: Not 500, it was 219
  -> explicit correction parser sees old=500 and new=219
  -> model/search identifies the exact target
  -> backend creates an update proposal or applies update
```

### Mistaken transaction

```text
User: Delete that mistake
  -> model returns delete with transaction_id
  -> backend checks ownership and current state
  -> deleted_at is set
```

### Multiple transactions

```text
User message
  -> AI returns several draft_id items
  -> backend validates the whole array
  -> review mode shows all items together
  -> automatic mode applies all items atomically
```

## 24. Migration history relevant to capture

The current capture-related schema changes are:

| Migration | Change |
| --- | --- |
| `4f3b9c6d1a2e` | Adds `accounts.is_default` and selects a default Spending Account where needed. |
| `6a8e21b4d390` | Adds review mode, user timezone, new financial event states, assistant message links, event revisions, and capture receipts. |

The current database head is `6a8e21b4d390`.

Apply migrations with:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

The backend requirements include `tzdata` because Windows may not provide the IANA timezone database required by `zoneinfo`.

## 25. Current guarantees and boundaries

The capture system currently guarantees:

- No automatic write in review mode.
- No partial write when a batch fails validation.
- User-scoped entity and transaction access.
- Explicit amount preservation.
- Explicit draft continuity.
- Soft archive instead of physical deletion.
- Idempotent capture retries.
- Stale proposal detection.
- Persistent event and message history.
- Separate clarification and review states.

The following remain outside the capture implementation:

- Account balances.
- Reports and dashboard aggregates.
- Receipt OCR.
- Voice input and transcription.
- External bank or UPI integrations.
- Background processing and notifications.

Capture is therefore responsible for understanding and recording transaction events. Reporting can consume the resulting `transactions`, `transaction_groups`, and related entities without needing to understand the conversational AI process.
