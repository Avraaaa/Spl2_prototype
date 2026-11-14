P4-T2b — two UI defects found by the orchestrator in a real browser after P4-T2 merged (2026-11-15). Fix only these.

1. Stale identity after sign-in (BLOCKING). Repro: signed in as nwd.officer, signed out, signed in as ds.support; the page
   still renders "Welcome, Nadia… Issue Officer" and the previous header until a full page reload. After a reload it is
   correct. Cause: apps/web/src/features/auth/session.ts resetSession() calls queryClient.clear() and then
   setQueryData(ME_KEY, user). In TanStack Query v5, clear() removes Query objects that mounted observers (useMe in App,
   Shell, LoginPage) are still subscribed to, so the new data lands in a NEW query those observers never see.
   Fix: do NOT use clear() for this. E.g. `qc.setQueryData(ME_KEY, user)` and then
   `qc.removeQueries({ predicate: q => q.queryKey[0] !== ME_KEY[0] })` (or resetQueries for the rest), so the identity
   observers update immediately and all other user data is dropped. On logout set ME to null the same way. Update
   session.test.ts to prove that an existing ME observer receives the new user (use a real QueryClient and a
   QueryObserver subscribed before the reset), and that other cached queries are removed.

2. Premature validation banner (minor). apps/web/src/features/issues/IssueDraftPage.tsx `set()` does
   `setErrors(c => ({ ...c, [key]: undefined }))`, which leaves keys with undefined values, and hasErrors() counts keys, so
   "Please fix the highlighted fields." appears while typing before any submit. Fix: delete the key instead (or make
   hasErrors count only truthy messages) and only show the banner after a save/submit attempt. Add a vitest case to draftForm.test.ts.

Keep all other behaviour unchanged. Run `npm run --prefix apps/web check` and `node scripts/dev.mjs test` yourself and finish green.
