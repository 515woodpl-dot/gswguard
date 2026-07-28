# YorGuard private HTTPS on the Raspberry Pi

The Pi uses Tailscale Serve so YorGuard is reachable only by devices in the
tailnet:

- Dashboard: `https://gsw.tail8a6b99.ts.net`
- API: `https://gsw.tail8a6b99.ts.net:8443`

Tailscale terminates HTTPS and proxies to the local Docker services:

- dashboard `127.0.0.1:3000`
- API `127.0.0.1:8000`

## Pi configuration

Run these commands on the Pi after confirming that ports 3000 and 8000 are
healthy:

```bash
tailscale funnel reset
tailscale serve reset
tailscale serve --bg --https=443 http://127.0.0.1:3000
tailscale serve --bg --https=8443 http://127.0.0.1:8000
tailscale serve status
```

The expected status is:

```text
https://gsw.tail8a6b99.ts.net
  |-- / proxy http://127.0.0.1:3000
https://gsw.tail8a6b99.ts.net:8443
  |-- / proxy http://127.0.0.1:8000
```

Update the Pi's uncommitted `.env.local` values, preserving all existing
secrets:

```dotenv
API_BASE_URL=https://gsw.tail8a6b99.ts.net:8443
CORS_ORIGINS=https://gsw.tail8a6b99.ts.net
```

Then restart the Compose services:

```bash
docker compose up -d --build
curl -fsS https://gsw.tail8a6b99.ts.net:8443/health
curl -fsS https://gsw.tail8a6b99.ts.net/health
```

Do not enable Funnel for YorGuard. Funnel makes a service reachable from the
public internet; Serve keeps it inside the tailnet.

## Clients

The macOS receiver defaults to the API URL above. To install its automatic
LaunchAgent:

```bash
bash scripts/install-macos-receiver.sh
```

The Windows installer also defaults to the same API URL. The only per-computer
input remains the one-time enrollment token:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows-agent.ps1 -EnrollmentToken "ONE_TIME_TOKEN"
```

An explicit `-ApiBaseUrl` can still override the default for a different
tailnet or a local test server.
