# Review backlog (non-blocking findings)

Recorded by agent-runner (or the orchestrator) when a task PASSed with follow-ups. Prototype policy: only blocking defects fail a review; these are for a later hardening pass.

## P2-T1 — 2026-11-14
- [ ] Masking tests are spread across three modules; consolidate older cases into the table-driven module.
- [ ] Masking is heuristic (proximity rule for OTP/PIN, digit-run rule for cards). Re-evaluate with the P5 masking work (E-11..E-15) and add human mask review (E-13).

## P2-T2 — 2026-11-14
- [ ] [follow-up] services/api/domains/issues/api.py:115: Draft PATCH validates `version` before checking whether the actor can edit the draft. An invalid version on a non-editable issue returns 400 instead of the requested 403. Check edit permission and state first.
- [ ] [follow-up] services/api/domains/issues/workflow.py:243: Failed verification clears `actual_delivery_at`; reopening does the same. The delivery event retains the timestamp, but the issue detail then shows “Not delivered.” Show the prior delivery clearly in the UI.
- [ ] [follow-up] services/api/tests/test_p2_t2_workflow.py:304: Event access is tested for immutability, but not for cross-bank reads. Add a negative GET test for the event endpoint.
