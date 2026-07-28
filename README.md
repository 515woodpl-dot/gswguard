# YorGuard

YorGuard is a lightweight endpoint-management platform. The initial target is two company-owned Windows 11 Pro laptops, with a secure foundation for a small future fleet.

## Project status

The current prototype has a deployed Supabase-backed authentication and device-enrollment path, cross-platform receiver helpers, and a working Raspberry Pi dashboard. Several domain modules remain test-backed foundations rather than complete product workflows. See the [implementation audit](docs/audit-2026-07-28.md).

## Planned layout

```text
apps/                  Dashboard, FastAPI API, and Windows agent
packages/              Shared contracts and UI foundations
infrastructure/        Docker, DigitalOcean, and operational scripts
supabase/              Migrations, seed data, and database tests
docs/                  ADRs, architecture, security, and operations
.github/workflows/     CI and security checks
```

## Local checks

Requirements for the current phase: Node.js 20+ and npm. Run:

```text
npm run validate
```

Application-specific commands will be added only when each application exists. Windows-agent builds and Windows integration tests will run on the pinned Windows CI runner described in [ADR 0004](docs/adr/0004-windows-build-and-validation.md).

## Development sequence

The original phased order was Phase 1A → Phase 1C contract proof of concept → Phase 1B application skeletons. The implementation is now in integration and hardening work; each new bounded execution still requires explicit acceptance criteria and validation. See [the implementation plan](docs/implementation-plan.md) and the [implementation audit](docs/audit-2026-07-28.md).

## Security and governance

Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the [ADR index](docs/adr/0000-adr-index.md) before contributing.

# gswguard
