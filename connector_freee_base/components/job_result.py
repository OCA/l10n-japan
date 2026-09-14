# Copyright 2026 Takahiro SUNAGA <t.sunaga@takahii.co>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Shared helpers for formatting ``queue.job.result`` payloads.

Every freee feature module (invoice, future purchase/expense/pos)
formats its exporter / deleter return values the same way:

* A JSON-pretty-printed string keeps the value readable in the Job
  Queue UI without dropping Japanese characters
  (``ensure_ascii=False``);
* By default only a non-sensitive operational summary is stored in
  ``queue.job.result`` — the column is unencrypted Text and visible to
  any queue_job manager, a broader group than freee admin. The
  full request / response payload is added back only when the
  backend's admin / dev-mode ``debug_log_request_payload`` toggle is
  on.

Importing these from a single base module keeps every feature module's
job-result shape identical and stops the payload-redaction stance from
drifting per module.
"""

import json


def format_job_result(data):
    """JSON-pretty-print ``data`` for ``queue.job.result``.

    Used as the return value of every freee exporter / deleter ``run``.
    """
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def debug_payload(binding, request, response):
    """Return ``{"request", "response"}`` to merge into the job result,
    but only when the backend's debug toggle is enabled.

    Default ``{}`` keeps the redacted summary; turning the toggle on
    (admin, developer mode) re-exposes the exact data exchanged with
    freee in the Job Queue screen for troubleshooting. Remember to
    flip the toggle back off once done — it stays on until manually
    cleared.
    """
    backend = binding.backend_id
    if not backend.sudo().debug_log_request_payload:
        return {}
    return {"request": request, "response": response}
