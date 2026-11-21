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

## P4-T2 — 2026-11-14
- [ ] [follow-up] I reviewed the diff and key files but did not run the app in a browser or run the test suites. The gate results you supplied are the only test evidence.
- [ ] [follow-up] The new Issue serializer fields (names, references, organization) sit behind the existing tenant-scoped `visible_rows`. The new `organization`, `assignee` and `overdue` filters are applied after tenant scoping, so they can only narrow results. I found no cross-bank exposure.
- [ ] [follow-up] `IssueEventSerializer.get_assignee_name` runs a separate `User` query for each assignment event. This is an N+1 query pattern. Prefetch the assignees or cache them in the serializer context.
- [ ] [follow-up] `dashboard_counts` builds `by_bank` by looping over every issue row in Python. Replace it with a `values().annotate(Count())` aggregate. It only runs for DataSoft staff.
- [ ] [follow-up] `redirectFor` is UX-only. Django still enforces permissions, which is correct. Extend its unit tests to cover mixed-role edge cases, such as a user who is both Support Agent and Issue Officer.
- [ ] [follow-up] The `WorkflowActions.tsx` handlers are long single lines, which goes against the readability bar in the task. Reformat them.

## P4-T2b — 2026-11-14
- [ ] resetSession now calls setQueryData(ME_KEY, user) and then removeQueries for every key whose first element isn't 'auth'. A mounted ME observer therefore receives the new user, and logout sets null. This fixes defect 1.
- [ ] hasErrors now counts only truthy messages, and set() deletes the key instead of writing undefined. Together these fix the premature banner (defect 2).
- [ ] The new tests are real: session.observers.test.ts subscribes a QueryObserver before the reset and checks the cache is pruned. draftForm.errors.test.ts checks that `{ title: undefined }` is not an error. Both are in new files, and no existing tests were edited.
- [ ] I did not re-run the gates. The prompt reports validate-repo, makemigrations, check-contract, lint and test all exit 0.
- [ ] [follow-up] removeQueries keeps every query under the 'auth' key prefix, not just ME_KEY. If other auth-scoped queries are added later, they will survive a user switch. Match the full ME_KEY instead.
- [ ] [follow-up] I did not confirm in the diff that the banner is hidden until a save/submit attempt. Only hasErrors and set() changed; whether the banner is gated on an attempt flag is unverified.

## P7-T1 — 2026-11-21
- [ ] [follow-up] Custom regex validation blocks invalid syntax, long patterns, and one nested-quantifier form, but other potentially expensive expressions may still be accepted. Consider stronger regex restrictions or a timeout.
- [ ] [follow-up] Tests cover tenant isolation for original issue text and masking before attachment NLP, but do not directly verify cross-tenant attachment downloads or audit-chain verification.
