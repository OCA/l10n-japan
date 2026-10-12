1. In the freee developer console, register an application and note its
   *Client ID* and *Client Secret*. Two things must be configured on the
   freee app *before* you authorize the backend from Odoo:

   - **Callback URL** — add the redirect URI shown on the freee Backend
     form to the application's allowed callbacks. The exact value is

     ```
     <your Odoo URL>/freee/oauth/callback
     ```

     (e.g. `https://erp.example.co.jp/freee/oauth/callback`). The
     Backend form computes this from the *System Parameter*
     `web.base.url`, so make sure that points at the public URL of the
     Odoo instance before clicking *Authorize with freee*.
   - **Application scopes** — tick exactly the scopes this
     connector uses, no more, no less. The full table (read-only vs.
     read-and-update) is in `readme/USAGE.md` under *Required freee
     application scopes*. Missing scopes do not block authorization —
     they fail later, when a wizard or export job hits the endpoint
     they were supposed to cover.
2. In Odoo, go to **Connector → freee → Backends** and create a record
   for the company you want to synchronise.
3. Paste the Client ID and Client Secret. Save the record.
4. Click **Authorize with freee**. You will be redirected to freee, asked
   to grant access, and sent back to the backend form. The state should
   become *Authorized*.
5. Click **Test Connection** to confirm the access token works.

Tokens are stored encrypted at rest with a Fernet key you must provide
in `odoo.conf`, under `[options]`:

```ini
connector_freee_base_encryption_key = <Fernet key>
```

Generate a key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The key is read from `odoo.conf` only — it is **not** generated
automatically and **not** stored in the database, so it never lands in a
`pg_dump`. If it is missing when a credential is saved or an export runs,
the connector raises a clear error instead of running unprotected.
Restart Odoo after adding or changing it, back up `odoo.conf` separately
from the database, and see `readme/RUNBOOK.md` for rotation.
