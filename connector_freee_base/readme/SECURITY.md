# freee Connector — Security Notes

State this plainly to whoever signs off on production use. Nothing here is a defect; it
is the **threat model** the connector actually provides, so the decision to accept it is
made knowingly.

## Stored credentials

These freee secrets are stored encrypted, never in plaintext columns:

- `client_secret`
- `access_token`
- `refresh_token`

Encryption is Fernet (AES-128-CBC + HMAC, `cryptography` library). Plaintext is exposed
only through compute fields gated behind the `connector_freee_base.group_freee_admin`
group.

## What the encryption does and does NOT protect

The Fernet key is read from `odoo.conf` under `[options]`, key
`connector_freee_base_encryption_key` — i.e. **outside the database it protects**. It is
never generated automatically and never written to the DB; a missing key raises a clear
error rather than starting unprotected.

Therefore it defends against:

- **Database dumps / backups** read offline: a `pg_dump` or stolen backup file does
  **not** contain the key, so the encrypted tokens in it cannot be decrypted without also
  obtaining `odoo.conf`.
- **Casual / accidental reads** of the credential columns by users without the freee
  admin group.

It does **not** defend against:

- A **compromised live Odoo host or process**: anything that can read `odoo.conf` (or the
  running process memory) can read the key and decrypt the tokens. Protect `odoo.conf`
  file permissions accordingly.
- A malicious user who already has the `group_freee_admin` group (they can read the
  decrypted values by design).

This is a deliberate, modest threat model appropriate for an Alpha internal connector. A
stronger posture (external KMS / per-tenant key) is explicitly out of scope for now and
is recorded in `readme/ROADMAP.md`.

## Key loss

The key is **not recoverable** if the `odoo.conf` entry is lost or changed.
Consequence: all stored ciphertext becomes undecryptable and **every freee backend must
be re-authorized** (re-run the OAuth flow). There is no key escrow.

Operational guidance:

- Back up `odoo.conf` **separately** from the database — a DB backup no longer carries
  the key. Both are needed to restore working credentials.
- After a restore (or a key change), if backends show authorization errors, expect to
  re-authorize them; this is the documented failure mode, not a bug.

## Transport

All freee API calls are HTTPS to `api.freee.co.jp` / `accounts.secure.freee.co.jp`. The
`api_base_url` / `oauth_base_url` fields are operator-editable but **validated**: a
model constraint rejects any value that is not `https://` on `freee.co.jp` or a
`*.freee.co.jp` sub-domain, so the bearer token / client secret cannot be redirected to
a non-freee host. OAuth uses the authorization-code flow with a CSRF `state` nonce;
the redirect URI is fixed per backend.

## Job results & logs

`queue.job.result`, `queue.job.exc_message` and the binding's `sync_error` are
unencrypted columns readable by queue_job managers (a broader group than freee admin).
The connector therefore stores only a **non-sensitive operational summary** there
(method, endpoint, freee deal id, detail count, status) — never the deal request payload
or freee's verbatim response body, which carry partner / amounts / per-line text. The
adapter logs the same summary, not the payload. A failed job's `sync_error` still
keeps freee's error message (needed to fix the failure) but no request payload.

**Debug escape hatch.** The backend has a `debug_log_request_payload` boolean
(freee-admin-only, and only visible on the form in developer mode), **off by default**.
When an operator turns it on, each subsequent export/delete job's `result` _also_
contains the full request payload sent to freee and freee's raw response — so "what is
actually being sent" can be inspected from Settings → Technical → Queue Job. This
deliberately re-exposes partner / amounts / per-line text in the unencrypted result
column, so it is a conscious, temporary troubleshooting action: turn it on, reproduce
the issue, turn it off. It does not change `sync_error` or the adapter logs. Leave it
**off in production** — confirm it is off before relying on the connector.
