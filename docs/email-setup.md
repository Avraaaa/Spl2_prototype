# Account email setup

The portal sends account credentials and password reset links through Django's existing email outbox. Configure Resend's SMTP relay with environment variables; the app never reads `.env` files.

1. Create a Resend account, add a sending domain, and complete the DNS verification steps shown by Resend.
2. Create an API key with permission to send email.
3. Set `RESEND_API_KEY`, `EMAIL_FROM` to an address on the verified domain, optional `EMAIL_REPLY_TO`, and `PORTAL_BASE_URL` in the deployment environment. `PORTAL_BASE_URL` is the public portal origin used in reset links.
4. Restart the API. Without `RESEND_API_KEY`, Django uses its console email backend and emits one startup warning.
5. Run `node scripts/dev.mjs manage send_test_email --to <addr>` to verify delivery through the selected backend. The console fallback prints the test message locally.

The SMTP relay is `smtp.resend.com:587` with STARTTLS and username `resend`. `RESEND_API_KEY` is used as the SMTP password. Do not put secrets in source control or logs. Outbox delivery is retried by the existing worker; account email messages remain visible there until sent or terminally failed.
