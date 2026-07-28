# YorGuard API

The FastAPI service exposes health, authenticated membership, enrollment, heartbeat, and device-inventory routes. Inventory, jobs, compliance, package, file-operation, notification, and audit modules currently remain test-backed integration work.

From the repository root, after installing the API requirements:

```text
python3 -m pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload
```

The API imports the shared contract source and returns structured health responses. Readiness checks the configured database. The global exception handler returns sanitized error envelopes and never exposes exception details.
