# YorGuard private HTTPS on the Raspberry Pi

The Pi uses Tailscale Serve so YorGuard is reachable only by devices in the
tailnet:

- Dashboard: `https://gsw.tail8a6b99.ts.net:10000`
- API: `https://gsw.tail8a6b99.ts.net:8443`

Tailscale terminates HTTPS and proxies to the local Docker services:

- dashboard `127.0.0.1:3000`
- API `127.0.0.1:8000`

Both containers publish on the loopback interface only
(`127.0.0.1:8000:8000` and `127.0.0.1:3000:3000` in `docker-compose.yml`).
That is load-bearing, not cosmetic: publishing on `0.0.0.0` put the API — including
`/api/v1/devices/enroll`, `/devices/heartbeat` and `/devices/inventory`, which
carry enrollment tokens and device credentials — on the local network over
plaintext HTTP, bypassing this whole HTTPS boundary. Verify after any Compose
change:

```bash
ss -tlnp | grep -E '3000|8000'      # must show 127.0.0.1, never 0.0.0.0 or ::
curl -m 5 "http://$(hostname -I | awk '{print $1}'):8000/api/v1/health/ready"   # must fail to connect
```

## Pi configuration

Run these commands on the Pi after confirming that ports 3000 and 8000 are
healthy. The existing slideshow keeps the default HTTPS/Funnel route on port
443; YorGuard uses private Serve on ports 10000 and 8443:

```bash
tailscale serve --https=443 off
tailscale funnel --bg --yes 5001
tailscale serve --bg --yes --https=10000 3000
tailscale serve --bg --yes --https=8443 8000
tailscale serve status
```

The expected status is:

```text
https://gsw.tail8a6b99.ts.net (Funnel on; slideshow)
  |-- / proxy http://127.0.0.1:5001
https://gsw.tail8a6b99.ts.net:10000 (tailnet only; YorGuard dashboard)
  |-- / proxy http://127.0.0.1:3000
https://gsw.tail8a6b99.ts.net:8443
  |-- / proxy http://127.0.0.1:8000
```

Update the Pi's uncommitted `.env.local` values, preserving all existing
secrets:

```dotenv
API_BASE_URL=https://gsw.tail8a6b99.ts.net:8443
CORS_ORIGINS=https://gsw.tail8a6b99.ts.net:10000
```

Then restart the Compose services:

```bash
docker compose up -d --build
curl -fsS https://gsw.tail8a6b99.ts.net:8443/api/v1/health/ready
curl -fsS https://gsw.tail8a6b99.ts.net:10000/health
```

Funnel is reserved for the existing slideshow on port 5001. Do not attach
YorGuard to Funnel; its dashboard and API remain tailnet-only through Serve.

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
