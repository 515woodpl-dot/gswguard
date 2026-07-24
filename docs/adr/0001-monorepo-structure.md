# ADR 0001: Monorepo structure and repository boundary

- Status: Proposed
- Date: 2026-07-24

## Context

GSWGuard needs coordinated dashboard, API, Windows agent, contracts, migrations, infrastructure, and documentation. The supplied workspace is a Playground directory containing unrelated projects and is not itself a Git repository. No existing GSWGuard repository was discoverable.

## Decision

Use a dedicated GitHub repository and monorepo rooted at `GSWGuard/` in the current workspace. During this execution, only architecture documentation is created. Application code begins only after the Phase 0A review gate. The intended layout is:

```text
GSWGuard/
├── apps/{dashboard,api,windows-agent}/
├── packages/{contracts,ui}/
├── infrastructure/{docker,digitalocean,scripts}/
├── supabase/{migrations,seed,tests}/
├── docs/{adr,architecture,security,operations}/
├── .github/workflows/
├── .env.example
├── docker-compose.yml
├── README.md
└── SECURITY.md
```

The project must not modify sibling Playground projects. A Git repository should be initialized or connected to the owner’s empty GitHub repository as a separate, owner-approved repository setup action before Phase 1A.

## Consequences

Boundaries stay explicit and releases can coordinate API/agent contracts. The current workspace does not provide GitHub remote identity, branch protection, or repository ownership, so those remain deployment/governance decisions.
