## Pick the freee company on the backend

Once the backend has been authorized (see *Configuration* for the
OAuth setup), click **Fetch Companies** on the backend form to load
`/api/1/companies`. Pick the row matching the freee company you
want this backend to drive, and click *Use this*. The freee
`company_id` is stored on the backend — it is not exposed in the
freee web UI; this wizard is the only way to discover it.

Click **Test Connection** to verify the bearer token reaches
`/api/1/companies/{company_id}` successfully.

## Required freee application scopes

The freee OAuth application backing this connector must request the
exact scopes below — every other scope can stay unticked. Set them in
the freee developer console (*App → Scopes* tab) **before**
authorizing the backend, otherwise the master-data sync wizards (next
section) will fail with HTTP 403 even when the access token itself is
valid.

**Read-only — used by the fetch wizards and *Verify
Configuration*:**

| freee scope (Accounting) | What this connector reads it for                                |
|--------------------------|------------------------------------------------------------------|
| Account items            | `GET /api/1/account_items` — map Odoo *Chart of Accounts* / journals |
| Companies                | `GET /api/1/companies` (and `…/{id}`) — bind backend, *Test Connection* |
| Items                    | `GET /api/1/items` — map Odoo *Products*                          |
| Partners                 | `GET /api/1/partners` — map Odoo *Contacts*                       |
| Sections                 | `GET /api/1/sections` — map Odoo *Analytic Accounts*              |
| Tax classifications      | `GET /api/1/taxes/companies/{company_id}` — map Odoo *Taxes*      |
| Walletables              | `GET /api/1/walletables` — map Odoo *Journals* (settlement account) |

**Read + update — used by invoice export:**

| freee scope (Accounting) | What this connector writes there                              |
|--------------------------|----------------------------------------------------------------|
| Deals                    | `POST` / `PUT` / `DELETE /api/1/deals` — the actual invoice export |

That is the entire surface: every other freee resource is left alone.
Granting fewer scopes silently breaks whichever wizard or job hits the
missing one; granting more is unnecessary.

After changing scopes on the freee side you must re-authorize the
backend (Connectors → freee → Backends → *Authorize with freee*) — the
issued access token bakes the scopes in, so an existing token keeps
the old, narrower set even after the app definition has changed.

## Sync master data with freee

Before any feature module (e.g. `connector_freee_invoice`) can push
records to freee, a few Odoo records must be mapped to their freee
counterparts. Each mapping uses the same *fetch + select* wizard
pattern:

1. Open the Odoo record (account, tax, partner, …).
2. Scroll to the **freee Mapping** group (visible only to *freee
   Administrator*).
3. Click **Pick from freee** to open the wizard.
4. Pick the target **freee Backend** (defaults to the first
   authorized backend).
5. Click **Fetch from freee** — the wizard calls the corresponding
   `GET /api/1/...` endpoint and populates the list.
6. Click **Use this** on the row you want to bind. The freee id (and
   freee name, where applicable) is written onto the Odoo record.

The supported masters are:

| Odoo model              | Field(s) written                                       | freee endpoint                          | Where to find it                                 |
|-------------------------|--------------------------------------------------------|------------------------------------------|--------------------------------------------------|
| `account.account`       | `freee_account_item_id`, `freee_account_item_name`     | `/api/1/account_items`                   | Accounting → Configuration → Chart of Accounts   |
| `account.journal`       | `freee_account_item_id`, `freee_account_item_name`     | `/api/1/account_items`                   | Accounting → Configuration → Journals → *freee Mapping* tab — **optional**, see *Splitting sales by journal* below |
| `account.journal`       | `freee_walletable_id`, `freee_walletable_type`, `freee_walletable_name` | `/api/1/walletables`     | Accounting → Configuration → Journals → *freee Mapping* tab (settlement account) — **optional**, see *Settling via a walletable* below |
| `account.tax`           | `freee_tax_code`, `freee_tax_name`                     | `/api/1/taxes/companies/{company_id}`    | Accounting → Configuration → Taxes               |
| `res.partner`           | `freee_partner_id`, `freee_partner_code`, `freee_partner_name` | `/api/1/partners` (optional `keyword` filter) | Contacts → form view                             |
| `product.template`      | `freee_item_id`, `freee_item_name`                     | `/api/1/items`                           | Accounting / Invoicing → Customers → Products (or Sales / Purchase / Inventory if installed; see *Reaching the product form* note below) |
| `account.analytic.account` | `freee_section_id`, `freee_section_name`     | `/api/1/sections`                        | Accounting / Invoicing → Configuration → Analytic Accounts (see *Analytic Accounting* note below) |

Re-running a wizard always replaces its previous list — pick from
the freshly fetched data, not stale rows. The wizards do not write
to freee; they only *read* from freee and store the chosen id on
the Odoo side.

### Splitting sales by journal — `account.journal` mapping

Sales fed through different Odoo journals — e.g. manually raised
customer invoices vs. an EC-site sales journal — sometimes need to
land on **different freee account items** so the two streams stay
separable in freee, even when they post to the same Odoo income
account.

The exporter resolves each deal line's `account_item_id` with this
precedence:

1. the **line's income account** `freee_account_item_id` (if set) —
   the natural Odoo account ↔ freee account mapping, used in the vast
   majority of cases;
2. otherwise the **invoice's journal** `freee_account_item_id` (if
   set) — the per-journal/walletable fallback that lets you split
   sales by journal;
3. otherwise the export fails with a `MappingError` naming both.

To split sales by journal, **leave the shared Odoo account
intentionally unmapped** (e.g. clear `freee_account_item_id` on the
shared Sales account) and set the freee account item on each journal
instead. Open *Accounting → Configuration → Journals*, pick the
journal (e.g. the EC sales journal), and on the *freee Mapping* tab
use *Pick from freee* exactly like the chart of accounts. Lines
posting to the shared account then resolve their freee account item
from whichever journal carried the invoice.

When the account is mapped, the journal-level value is ignored — so
journal mapping is an opt-in fallback, never a silent override of the
per-account configuration.

### Settling via a walletable (account) — `account.journal` mapping

By default every exported deal is **unsettled** — freee
records the income/expense but no payment. To have invoices on a
given journal exported as **settled** (paid), map a freee walletable
(account) onto that journal:

*Accounting → Configuration → Journals* → pick the journal → *freee
Mapping* tab → **settlement account** → *Pick walletable from freee*
(loads `/api/1/walletables`: bank account / credit card / cash) →
*Use this*. *Clear (→ unsettled)* removes the mapping.

Effect on export:

- **walletable mapped** → the deal carries one `payments[]` entry for
  the full tax-inclusive total, `from_walletable_id` /
  `from_walletable_type` from the mapping, dated the invoice's
  *Invoice Date* (the connector does not track real settlement timing
  — it books the payment on the issue date, a deliberate
  simplification);
- **walletable not mapped** (the default) → no `payments` is sent and
  freee keeps the deal unsettled — unchanged behaviour;
- **refunds (`out_refund`)** on a journal with a walletable settle the
  same way but with a **negative** `payments[].amount` (money flowing
  back out); with no walletable they stay unsettled.

This is independent of the account-item split above: a journal can map
a walletable, an account item, both, or neither.

### Required permissions

Two layers of access apply to every mapping:

- **freee Administrator** (`connector_freee_base.group_freee_admin`)
  — gates the *freee Mapping* group on every form (the freee fields
  and the *Pick from freee* button are hidden without it). All five
  fetch wizards also live behind this group.
- **The native Odoo group required to edit the underlying record.**
  Picking a freee Mapping is a write on the Odoo record, so the
  user also needs whatever Odoo normally requires to edit that
  model:

  | Odoo model                  | Required Odoo group                                                          |
  |-----------------------------|------------------------------------------------------------------------------|
  | `account.account`           | *Accounting → Show Full Accounting Features* (`account.group_account_manager`) |
  | `account.tax`               | *Accounting → Show Full Accounting Features* (`account.group_account_manager`) |
  | `account.analytic.account`  | *Accounting → Analytic Accounting* (`analytic.group_analytic_accounting`)    |
  | `res.partner`               | Standard internal user                                                       |
  | `product.template`          | Any group with `product.template` write access — granted by *Sales*, *Purchase* or *Inventory* (the base `product` module alone has no UI) |

In particular, mapping the **Chart of Accounts** (and **Taxes**)
requires *Show Full Accounting Features* — *Billing* alone is not
enough. A user with only *freee Administrator* but without the
right accounting group will see the *Pick from freee* button but
the wizard's *Use this* save will fail with a standard Odoo access
error.

### Reaching the product form

The core `product` module defines `product.template` but does
**not** register a top-level *Products* menu on its own. Several
consumer apps register one — pick whichever your install already
has:

- **Accounting / Invoicing → Customers → Products** — provided by
  the `account` module, which is a hard dependency of
  `connector_freee_base`, so this path is **always available**.
  It is the recommended entry point on a minimal install.
- **Sales → Products → Products** — same records, but with the
  Sales-app extras (price lists, optional products, sales tab).
- **Purchase → Products → Products** — same records, with the
  Purchase-app extras.
- **Inventory → Products → Products** — same records, with stock
  / variants / routes.

All four menus are views over the same `product.template` data,
so the *freee Mapping* group appears in any of them. Item
mapping is optional — invoices export fine without
`freee_item_id` set on the line's product.

### Showing the Analytic Accounting menu

The *Analytic Accounts* menu is hidden by default in stock Odoo
(both Community and Enterprise). If you cannot find *Analytic
Accounts* under **Accounting → Configuration** (Enterprise) or
**Invoicing → Configuration** (Community), enable it like this:

1. Open **Settings → Users & Companies → Users**, pick the user.
2. Under the **Accounting** rights, tick **Analytic Accounting**
   (this assigns the `analytic.group_analytic_accounting` group).
3. Save and refresh the browser. The *Analytic Accounts* menu
   appears under the Accounting / Invoicing app's *Configuration*
   submenu, next to *Chart of Accounts* and *Taxes*.

This module installs on Odoo Community as well as Enterprise — it
depends only on the `account`, `analytic` and `product` core
modules plus the OCA `connector` and `queue_job` modules, none of
which are Enterprise-only. The menu label differs between
editions (*Accounting* vs *Invoicing*) but the configuration
submenu and the *freee Mapping* group on each form work the same
way.

## Programmatic access

The API client is reachable through a connector work context:

```python
backend = env["freee.backend"].search(
    [("state", "=", "authorized")], limit=1
)
with backend.work_on(backend._name) as work:
    adapter = work.component(usage="backend.adapter")
    me = adapter.get("/api/1/users/me")
    sections = adapter.get(
        "/api/1/sections",
        params={"company_id": backend.external_company_id},
    )
```

The adapter accepts `get`, `post`, `put`, `delete` and returns the
decoded JSON body. Transient errors (HTTP 429, 5xx, network
failures) raise `RetryableJobError`, so calls dispatched through
`queue_job` retry automatically.
