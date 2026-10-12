# freee Connector Base — Operations Runbook

Operational notes for the base layer: encryption key handling, OAuth
token rotation, and recovery from common failure modes. Feature-module
RUNBOOKs (e.g. `connector_freee_invoice/readme/RUNBOOK.md`) reference
this one for the credential side and stay focused on their own export
flow.

---

## 1. Back up the encryption key

The Fernet key that decrypts `client_secret`, `access_token` and
`refresh_token` is read from `odoo.conf` under `[options]`:

```
connector_freee_base_encryption_key = <Fernet key>
```

You set it once at install (generate with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
and it is **never rotated automatically**. Two things follow:

1. **A DB backup does NOT cover it** — the key lives in `odoo.conf`, not
   the database, so it is absent from any `pg_dump`. Back up `odoo.conf`
   separately; both the DB and `odoo.conf` are needed to restore working
   credentials.
2. **Losing or changing the key makes every stored token undecryptable.**
   That is the documented failure mode (`readme/SECURITY.md`, *Key
   loss*), not a bug.

If you ever do lose or change the key, the recovery is:

- Delete the encrypted columns on every backend (`encrypted_client_secret`,
  `encrypted_access_token`, `encrypted_refresh_token`).
- Re-paste `client_secret` on each backend form.
- Click **Authorize with freee** to re-run the OAuth flow.

There is no key escrow; this is by design.

## 2. OAuth token rotation

freee's refresh tokens are **single-use** — every successful
`grant_type=refresh_token` exchange returns a new refresh token and
invalidates the previous one. The backend persists the rotated token
inside the same transaction, so a crash mid-rotation leaves the old
token in place (which freee will accept on the next try).

Concurrent refreshes are avoided at the deployment level rather than in
code: every freee export job runs on the capacity-capped `root.freee`
queue_job channel (configured `root.freee:1`), so at most one worker
hits the token endpoint at a time and freee's single-use refresh-token
rotation never races. Keep that channel at capacity 1.

Day-to-day:

- **Expected rotation cadence.** Tokens refresh transparently when an
  API call detects the access token has less than
  `TOKEN_REFRESH_LEEWAY_SECONDS` (5 min) of life left. There is no cron
  to schedule.
- **Symptoms of a stuck rotation.** If every freee job suddenly fails
  with HTTP 401 *and* the backend state flips to `unauthorized`, the
  refresh token has been invalidated outside our flow (most often:
  user re-authorized from the freee admin UI). Re-run the OAuth flow
  from the backend form.
- **Manual force-refresh.** Open the backend form as a freee
  administrator, click **Test Connection**. It does *not* force a
  refresh on its own, but exposes a stale-token state cleanly so you
  know whether to re-authorize.

## 3. When to revoke

Revoke (and re-authorize) the backend when:

- An operator with freee admin access leaves the team — they had
  permission to read decrypted tokens.
- A DB dump leaves the trusted operations boundary (e.g. shared with
  an external party). The key travels with the dump; treat the tokens
  as compromised.
- freee notifies you of unusual activity on the app.

Revoke flow: freee developer console → application → *Revoke* → in
Odoo, clear the backend's `encrypted_*` columns and re-authorize.

## 4. Observability quick-reference

- **`queue.job` / `queue.job.result`** — operational summary per
  export, retained per Odoo's queue-job lifecycle. Never the request
  payload (unless `debug_log_request_payload` is on; keep it off in
  production — see `readme/SECURITY.md`).
- **Server log (`INFO`)** — the same summary, plus token-refresh
  events. The token endpoint's error body is *suppressed*; only the
  OAuth `error` / `error_description` codes appear.
- **Backend form → *State*** — `unauthorized` / `authorized` /
  `error`. Flip to `error` is your "investigate now" signal.
