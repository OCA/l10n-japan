This module is the base layer of an OCA-style connector for the freee
Accounting cloud service. It provides:

- A `freee.backend` model that represents an authenticated freee company
  binding (multi-company aware).
- An OAuth 2.0 Authorization Code flow with transparent access-token refresh.
- An encrypted credential store for client secrets and refresh tokens.
- A `backend.adapter` component — reusable across freee feature modules
  within this connector family — that wraps the freee REST API and maps
  HTTP errors onto the `queue_job` retry semantics (429 / 5xx / network
  failures become `RetryableJobError`).
- A `freee.export.mapper` abstract base component that every freee
  feature module's export mapper inherits — it bundles the freee
  collection and `export.mapper` usage, plus master-data resolution
  helpers that turn Odoo master records (account, tax, analytic
  account, product, partner) into the freee ids stored on them by the
  picker wizards, so every feature module maps master data identically.

It is intended to be the dependency for freee feature modules — siblings
that depend on this base directly and never on each other — which
synchronise specific business objects (e.g. customer invoices,
purchases, expenses) to freee.
