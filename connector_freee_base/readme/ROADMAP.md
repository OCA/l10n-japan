`connector_freee_base` is **Alpha** — we're shipping it to gather
early-adopter reactions. Known limitations and deliberate deferrals, so
adopters decide knowingly:

- **No automated test exercises a real freee company.** Every test
  mocks the HTTP layer, so the OAuth flow, token refresh and API
  client are proven for parsing and control flow, **not** against a
  live freee company. A pilot against a real freee company is required
  before any customer rollout — see the RUNBOOK of the freee feature
  module you adopt (e.g. invoice export) for the pilot checklist.

- **Encryption posture is modest by design.** Client secret, access
  token and refresh token are Fernet-encrypted. The key lives in
  `odoo.conf` (read via `tools.config`), so it is kept **out of the
  database** and absent from any `pg_dump` — this defends DB dumps and
  casual reads, **not** a compromised live host that can read
  `odoo.conf` or process memory. Losing the key forces re-authorization
  of every backend. An external-KMS / dedicated secrets-manager option
  is out of scope for now. Full threat model in
  `connector_freee_base/readme/SECURITY.md`.

- **Master-data mapping is consumed but not auto-resolved.** The
  picker wizards store freee ids on the Odoo master records
  (`freee_account_item_id`, `freee_tax_code`, `freee_partner_id`,
  `freee_item_id`, `freee_section_id`, journal walletable /
  account-item overrides); the shared mapper (reused across freee
  feature modules
  within this connector family) consumes them with documented
  precedence (see USAGE) but does not auto-match Odoo records to
  freee masters.
