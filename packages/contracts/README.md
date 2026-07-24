# Shared contracts

The Phase 1C proof of concept uses Pydantic models in `poc/source.py` as the temporary transport source. The generator emits an OpenAPI 3.1 document, TypeScript types, C# transport DTO fixtures, and JSON fixtures for required, optional, nullable, enum, UUID, and date-time mappings.

Run from the repository root:

```text
python3 scripts/generate_contract_poc.py
npm run contracts:check
npm run contracts:test
```

The final HTTP source remains FastAPI-generated OpenAPI as recorded in ADR 0002. FastAPI is not installed in this Phase 1C-only workspace, so this proof uses Pydantic’s schema output and will be revalidated against the FastAPI-generated document in Phase 1B. Generated files are never manually edited.
