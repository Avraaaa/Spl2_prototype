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

## P7-T5 — 2026-11-21
- [ ] [follow-up] Topic clustering falls back to keyword groups when no current-version vectors exist, and those groups can contain only two issues. P7-T5 specifies vector proposals only for at least 20 eligible requests and clusters of at least three; consider skipping proposals until those conditions are met.
- [ ] [follow-up] The new tests cover tenant-scoped label examples and search results, but do not directly verify cross-bank topic-cluster isolation, masking on draft edits/submission, or stale-job handling.
- [ ] [follow-up] The evaluation command compares lexical, dense, and RRF rankings on synthetic fixture records, but does not exercise the production candidate retrieval path or its minimum-relevance gate.

## P7-T6 — 2026-11-21
- [ ] [follow-up] The normalization test checks that lexical HitRate@5 does not regress on a single sample, but both normalized and baseline scores are already 1.0; it does not demonstrate a normalization benefit or exercise ranking with the fake embedder required by the task plan.
- [ ] [follow-up] Local GTE checkpoints enable `trust_remote_code`, which executes checkpoint-provided code. Keep this restricted to trusted local checkpoints and document that trust assumption.

## P7-T2 — 2026-11-21
- [ ] [follow-up] The deployed-version form asks admins to enter a client organization ID manually; an organization selector would reduce entry errors.
- [ ] [follow-up] Response due dates use the timestamp’s direct `.date()` value, while report dates use local time. Near-midnight submissions could display a due date one day off from the portal’s local date.
- [ ] [follow-up] The new tests cover bank isolation and a configured overdue period, but do not cover support-agent read access to cross-bank deployment history or the exact due-date boundary.

## P7-T3 — 2026-11-22
- [ ] [follow-up] Existing attachment rows with legacy status "unscanned" become non-downloadable (HTTP 423) because the download check requires CLEAN. Migration 0002 only changes the field default and does not backfill or rescan old rows.
- [ ] [follow-up] The scanner only checks for the EICAR signature. The plan's "type/size check" is covered by the existing checked_file validation, and the scanner is a plain function rather than a configurable plug-in point.
- [ ] [follow-up] Text attachments are read in full and decoded as UTF-8 after the scan. A non-UTF-8 .txt/.csv/.log file would raise a 500 on upload. The attachment record would already exist at that point with status CLEAN, but its stored file would not have been redacted.
- [ ] [follow-up] REJECTED files still persist in storage and in the attachment list (visible with status REJECTED). Only download is blocked. Consider purging them or hiding them from non-owners.
- [ ] [follow-up] Comments are masked with mask_sensitive and stored in event details. They are shown to everyone who can see the issue timeline, with no separate per-role comment visibility. This matches the existing event visibility rules.
- [ ] [follow-up] The tests cover comment storage, masking, EICAR rejection, clean download and cross-tenant download denial. There is no test that every workflow action accepts a comment, and none for a 423 response on a rejected file.

## P7-T4 — 2026-11-22
- [ ] [follow-up] Bangla tests rely on the existing seed fixture and a few hand-made cases. A larger Bangla/mixed fixture with graded relevance would give stronger evidence.
- [ ] [follow-up] The 360px layout fixes are CSS-only and have no automated check. They need a manual viewport check.
- [ ] [follow-up] Field errors set both role=alert and aria-live=polite, which is redundant. Screen readers may announce them twice.
