# YorGuard work completed — July 29, 2026

## Dashboard navigation

- Replaced anchor-style navigation with real left-panel workspace views:
  - Overview
  - Devices
  - Policies
  - Activity
- Kept fleet metrics on Overview and added quick-access cards to the other views.
- Prevented Devices, Policies, and Activity content from being repeated on the Overview page.
- Added responsive styling for the sidebar buttons and Overview quick cards.
- Removed stale one-page navigation and layout styles.

## Policy experience

- Simplified policy creation so users choose a policy name, the check to perform, and the required state.
- Added friendly labels for BitLocker, Firewall, Defender, Secure Boot, TPM, automatic updates, and Windows edition.
- Replaced free-form expected values with guided state choices.
- Generate the internal policy key automatically from the policy name and rule type.
- Clarified that policies are currently observation-only and do not perform automatic remediation.

## Verification

- Dashboard lint: passed.
- Dashboard typecheck: passed.
- Dashboard production build: passed.
- API tests: 40 passed.
- Windows agent build: passed with 0 warnings and 0 errors.
- Windows agent tests: 1 passed.
- Stale navigation/reference audit: no matches.
- Git diff check: passed.

The only test output was a non-blocking dependency warning about an older
`baseline-browser-mapping` dataset and an existing Starlette/httpx deprecation
warning in the Python test environment.

## Git

- Commit: `e3e35b4 Make dashboard navigation view-based`
- Branch: `agent/signed-update-chain`
- Pushed to: `origin/agent/signed-update-chain`

## Pi deployment status

The source batch is ready for the Pi. Deployment is pending because the current
Mac SSH agent has no identity loaded for `gsw@gsw`.
