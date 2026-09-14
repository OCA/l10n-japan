# freee API fixtures — provenance

Every JSON in this directory is a **verbatim** payload from the live freee Accounting
API, captured against a freee development company. List endpoints are trimmed to a
handful of records; everything else (field names, types, ordering, `null` markers) is
preserved exactly as freee returned it.

Tests feed these payloads through the mocked HTTP layer, so parsing is asserted against
real freee shapes rather than hand-written approximations. That means any claim about a
freee field's type or cardinality in the connector code can be back-traced to one of
these files.

| Fixture              | freee endpoint              | Captured against API version |
| -------------------- | --------------------------- | ---------------------------- |
| `account_items.json` | `GET /api/1/account_items`  | `2020-06-15`                 |
| `companies.json`     | `GET /api/1/companies`      | `2020-06-15`                 |
| `company.json`       | `GET /api/1/companies/{id}` | `2020-06-15`                 |
| `deal.json`          | `GET /api/1/deals/{id}`     | `2020-06-15`                 |
| `deals.json`         | `GET /api/1/deals` (LIST)   | `2020-06-15`                 |
| `items.json`         | `GET /api/1/items`          | `2020-06-15`                 |
| `partners.json`      | `GET /api/1/partners`       | `2020-06-15`                 |
| `sections.json`      | `GET /api/1/sections`       | `2020-06-15`                 |
| `taxes.json`         | `GET /api/1/taxes/codes`    | `2020-06-15`                 |
| `walletables.json`   | `GET /api/1/walletables`    | `2020-06-15`                 |

`2020-06-15` matches `FREEE_API_VERSION` in `connector_freee_base.models.freee_backend`,
the value the adapter sends on every request as `X-Api-Version`. Refresh fixtures (and
bump the table) only when that constant moves.
