# Reports architecture

Reports are read-only views of posted transaction data. The report layer lives in `app/modules/reports` and is independent of the capture provider. A future conversational reporting agent can call `build_report` with a validated `ReportFilters` object and cite the returned rows and totals; it should not recalculate financial figures from chat text.

## HTTP contract

- `GET /reports/options` returns accounts, categories, people and currencies available to the user, including archived entity names needed to filter historical transactions.
- `GET /reports/{view}` returns `metrics`, `trend`, `breakdowns`, paginated `rows`, `total`, `has_next`, and pivot columns. Supported views: `overview`, `spending`, `income`, `categories`, `accounts`, `people`, `activity`, `transfers`, `types`, `quality`, `pivot`.
- `GET /reports/export?view={view}` returns the current report's rows as UTF-8 CSV. It applies the same filters and exports all matching table rows rather than only the current page. The Overview table intentionally contains the ten largest expenses.

Shared query parameters: `date_from`, `date_to` (inclusive calendar dates in the user's timezone), `currency`, `account_id`, `category_id`, `person_id`, `type`, `direction`, `search`, `granularity`, `sort_by`, `sort_order`, `limit`, `offset`. Pivot reports also accept `pivot_row`, `pivot_column` and `pivot_measure`.

API amounts are decimal strings with two fractional digits. The client formats them for display. This avoids binary floating-point calculation in the report layer.

Overview, spending, income and category responses include a comparison when both date bounds are provided. It uses the immediately preceding interval of the same number of calendar days. Category comparisons use expense debits only. The API returns absolute differences; the client does not infer them from rounded display values.

## Source and definitions

The repository reads `transactions` joined to `transaction_groups`, `accounts`, `categories`, and `people`. Every query is scoped to the authenticated user. Only rows with `transactions.deleted_at IS NULL` and `transaction_groups.status = POSTED` are included. Archived accounts, categories and people remain visible by name on historical transactions. Dates are based on `transaction_date`, with inclusive `date_to` implemented as an exclusive midnight bound on the next local day.

One currency is selected per report. The system does not convert currencies or combine amounts from different currencies.

| Measure | Definition |
| --- | --- |
| Spending | `expense` + `debit` |
| Income | `income` + `credit` |
| Lent | `lend` + `debit` |
| Borrowed | `borrow` + `credit` |
| Repaid to you | `repayment` + `credit` |
| Repaid by you | `repayment` + `debit` |
| Net flow | Income − spending − lent + borrowed − repaid by you + repaid to you |
| Transfer volume | One amount per complete debit/credit transfer pair in a transaction group |
| Owed to you | Lifetime lent − lifetime repaid to you, through the selected end date |
| You owe | Lifetime borrowed − lifetime repaid by you, through the selected end date |
| Spent around a person | Selected-period expense debits linked to that person |

Outstanding person amounts intentionally ignore the selected start date, account, category, description search and transaction type: earlier loans still exist when reviewing one month. They respect currency, person and the selected end date. A negative owed amount can indicate an overpayment or incorrect transaction classification and is returned as-is rather than silently clamped.

Transfers are paired using `transaction_group_id`. A valid pair has two active transfer legs, opposite directions, the same amount and distinct accounts. Account filtering matches either side of the pair. Transfers are excluded from expense, income and net flow. Unpaired or inconsistent transfer legs are not counted as a complete transfer.

Type summaries count each complete transfer once. Pivot tables exclude transfers because a two-sided account movement has no single account attribution; the dedicated Transfers view presents the source and destination instead. There is no separate payment-method column in the current transaction model, so account and transaction type are the available dimensions for cash/UPI/bank style analysis.

The `quality` view identifies missing descriptions, uncategorized expense/income entries, archived account references, and missing people on lending/borrowing/repayment entries. Its capture counts are grouped from the user's financial events by event creation date.

## Frontend organization

`ReportsPage` owns the selected route, filters, data loading and export. `ReportFiltersBar` renders the shared search/date/entity filters. `ReportCharts` contains compact reusable chart components. `ReportTable` handles view-specific columns and pagination. A report view has its own route under `/app/reports/{view}` so the bottom navigation remains compact.

## Conversational reporting boundary

The future agent should translate a question into a report view and validated filters, invoke `build_report`, and explain the returned values with the selected period and currency. It must not execute arbitrary SQL or mutate transactions through Reports. The existing capture agent remains the mutation path. For an answer that needs more than one view, the agent can call the report service more than once and cite the scope of each result.

The current repository loads the user's matching transaction facts before aggregating them. This keeps all views on one set of definitions, but high-volume deployments should move the heaviest aggregations into SQL and stream large CSV exports. The public API and calculation rules can remain stable during that optimization.
