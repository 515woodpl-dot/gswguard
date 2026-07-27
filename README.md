# YorGuard

YorGuard is a lightweight endpoint-management platform. The initial target is two company-owned Windows 11 Pro laptops, with a secure foundation for a small future fleet.

## Project status

Phase 1B is complete: minimal dashboard, API, and Windows-agent skeletons are implemented. The database schema, authentication, enrollment, and device-management features are not implemented yet.

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

The approved order is Phase 1A → Phase 1C contract proof of concept → Phase 1B application skeletons. Each phase stops for owner review before the next begins. See [the implementation plan](docs/implementation-plan.md).

## Security and governance

Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the [ADR index](docs/adr/0000-adr-index.md) before contributing.

# gswguard
