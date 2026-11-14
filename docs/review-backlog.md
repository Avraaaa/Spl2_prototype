# Review backlog (non-blocking findings)

Recorded by agent-runner (or the orchestrator) when a task PASSed with follow-ups. Prototype policy: only blocking defects fail a review; these are for a later hardening pass.

## P2-T1 — 2026-11-14
- [ ] Masking tests are spread across three modules; consolidate older cases into the table-driven module.
- [ ] Masking is heuristic (proximity rule for OTP/PIN, digit-run rule for cards). Re-evaluate with the P5 masking work (E-11..E-15) and add human mask review (E-13).

## P2-T2 — 2026-11-14
- [ ] [follow-up] services/api/domains/issues/api.py:115: Draft PATCH validates `version` before checking whether the actor can edit the draft. An invalid version on a non-editable issue returns 400 instead of the requested 403. Check edit permission and state first.
- [ ] [follow-up] services/api/domains/issues/workflow.py:243: Failed verification clears `actual_delivery_at`; reopening does the same. The delivery event retains the timestamp, but the issue detail then shows “Not delivered.” Show the prior delivery clearly in the UI.
- [ ] [follow-up] services/api/tests/test_p2_t2_workflow.py:304: Event access is tested for immutability, but not for cross-bank reads. Add a negative GET test for the event endpoint.

## P3-T2 — 2026-11-14
- [ ] [follow-up] Verification reminders are keyed by calendar day, so an issue past the threshold can generate a reminder every day rather than once per configured reminder period.
- [ ] [follow-up] If an email send takes longer than the worker lease, another worker can claim and send the same message. The fixed Message-ID may help downstream deduplication, but the worker does not guarantee it.
- [ ] [follow-up] Tests cover delivery, rollback, retries, reminders, and personal API access, but do not directly check notification recipients for the other required workflow events.

## P3-T1 — 2026-11-14
- [ ] [follow-up] Attachment content checks inspect only the first 8 KB of text files; later binary content can pass validation.
- [ ] [follow-up] The task board can change status, but it has no controls to edit assignee or Git links after task creation.
- [ ] [follow-up] New tests cover two-bank access for comments and attachments, but do not directly test cross-bank task creation or every internal-note response path.

## P4-T1 — 2026-11-14
- [ ] [follow-up] CSV formula-injection guard only checks = + - @; it should also cover leading tab and carriage-return characters.
- [ ] [follow-up] detailed_rows reads issue.created_by.account.full_name directly; a creator with no account profile would raise a 500. This is unlikely for normal data.
- [ ] [follow-up] Summary and dashboard counts use per-status queries and Python loops. This is fine for a prototype but won't scale to large datasets.
- [ ] [follow-up] Recurring-link validation is duplicated in the serializer and in services._validate_links. Consolidating it would avoid the two copies drifting apart.
- [ ] [follow-up] The reports window filters on created_at only. Issues submitted or closed in the window but created earlier are excluded. This is acceptable under the spec's default.
