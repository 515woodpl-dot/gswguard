# Contributing to GSWGuard

## Workflow

- Use a feature branch for each bounded implementation unit.
- Open a pull request before merging to `main`.
- Keep `main` protected with required CI checks and no direct pushes.
- Prefer squash merges for small phase changes.
- Do not commit secrets, device credentials, provider keys, production signing material, or personal data.
- Include tests and documentation for behavior changes.

The owner’s conversational approval is the execution gate for Codex-assisted work. GitHub review is recommended repository governance but is separate from that gate.

## Phase discipline

Do not start a later phase because a placeholder would be convenient. Each phase report must state what was built, what was tested, what remains unvalidated, security concerns, and deferred decisions.

## Code boundaries

Keep generated contract code separate from domain models and never hand-edit generated output. API authorization must be enforced server-side. The Windows agent may execute only predefined, versioned handlers; arbitrary shell or user-supplied scripts are prohibited.
