# GSWGuard deployment runbook

## Preconditions

- Supabase project, migrations, RLS tests, and owner bootstrap procedure reviewed.
- DigitalOcean App Platform project and GitHub repository configured.
- Google Shared Drive/service account and Resend sender domain approved.
- Production secrets are entered only in DigitalOcean secret configuration.
- Windows agent artifacts are built and signed through the approved Windows workflow.

## Deployment

1. Run repository validation, application tests, dashboard build, and Windows CI.
2. Apply Supabase migrations through the controlled migration pipeline.
3. Confirm the production environment has `APP_ENV=production`, JWT issuer/secret, provider secrets, and no development bypass.
4. Deploy using `infrastructure/digitalocean/app.yaml` or an owner-reviewed equivalent.
5. Run `infrastructure/scripts/smoke.sh` against the deployed API and dashboard.
6. Verify logs contain no secrets, tokens, package bytes, or file contents.
7. Perform the manual two-device Windows 11 enrollment and heartbeat check.

## Rollback

Keep the previous application image/version available. Roll back the App Platform release if health checks fail, auth rejects known-good sessions, or package/file safeguards fail. Do not roll back database migrations destructively; use a forward migration or restore procedure reviewed by the owner.
