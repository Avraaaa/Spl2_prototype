Resume P2-T1. The seeded code is the complete P2-T1 implementation and has passed ALL five gates. The only open
review findings are about OTP masking: three review rounds each found a new phrasing that the phrase-specific regexes missed.
Stop adding phrase-specific regexes. Replace the OTP part of `mask_sensitive` in services/api/domains/issues/services.py with a
proximity rule, and keep everything else (attachments are P3-T1; do not add them).

Masking design (security invariant 6; heuristic, so human review remains required):
1. Card numbers (keep current behaviour): 13-19 digits, optionally separated by single spaces, dots or dashes -> `[CARD REDACTED]`.
2. OTP/PIN codes by proximity: a standalone 4-8 digit token (ASCII 0-9 or Bangla ০-৯ digits, not part of a longer number or word)
   is replaced with `[OTP REDACTED]` when a sensitive keyword occurs within 40 characters before OR after it, in the same sentence
   (do not cross `.`, `!`, `?`, `।` or a newline).
   Keywords (case-insensitive, whole words): otp, otp code, one-time password, one time password, one-time passcode, one-time code,
   verification code, security code, passcode, pin, tpin, mpin, ওটিপি, পিন, ভেরিফিকেশন কোড.
   NOT keywords on their own: "code", "error", "id", "version", "transaction", "ref".
3. Implement this with a small, readable function (find keyword spans, then check each digit-token span's distance). Do not rely on
   one giant regex.

Tests (table-driven, in the existing masking test module), covering both create_draft and edit_draft persistence:
- Must mask: "OTP: 123456", "OTP is 123456", "OTP for transfer: 123456", "OTP for transfer is 123456", "Use 123456 as your OTP",
  "123456 is the OTP", "the one-time password sent was 4821", "PIN 4321", "my tpin=9988", "verification code 77881",
  "ওটিপি ১২৩৪৫৬", "card 4111 1111 1111 1111", "card 4111.1111.1111.1111", "card 4111-1111-1111-1111".
- Must NOT mask: "Error 4012 on the transfer screen", "Release version 2024 fails", "Transaction 98765 failed. OTP was not sent",
  "error code 5001", "Account branch 1234 in the report header".
  (The digits in "Transaction 98765 failed. OTP was not sent" are in a different sentence from "OTP", so they stay.)
- Raw values never appear in the saved model fields or the API response.

Do NOT run uv/python/pytest/manage.py/dev.mjs/check-contract in your sandbox; the harness runs the gates.
