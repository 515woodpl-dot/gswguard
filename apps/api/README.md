# GSWGuard API

Minimal FastAPI skeleton. It exposes `/health/live`, `/health/ready`, and versioned equivalents under `/api/v1/`. Business modules and database integrations begin in later phases.

From the repository root, after installing the API requirements:

```text
python3 -m pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload
```

The API imports the Phase 1C contract source and returns structured health responses. The global exception handler returns sanitized error envelopes and never exposes exception details.
