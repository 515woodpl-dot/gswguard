# GSWGuard release checklist

- [ ] Phase review gates approved through the release scope.
- [ ] API tests, dashboard lint/typecheck/build, contract drift, and security scans pass.
- [ ] Windows CI build/tests pass; dedicated Windows 11 validation is complete.
- [ ] No secrets, tokens, device credentials, or production signing keys are in artifacts.
- [ ] Supabase migrations and RLS/pgTAP tests pass in a controlled project.
- [ ] Production JWT/bootstrap/role configuration reviewed.
- [ ] Google Shared Drive package/file permissions and hash/signature policies reviewed.
- [ ] Resend sender/recipient and notification deduplication reviewed.
- [ ] Backup and restore test evidence recorded.
- [ ] Smoke checks pass after deployment.
- [ ] Rollback version and incident contacts are documented.
