import type { HealthResponse } from '@gswguard/contracts/generated/typescript/health';
import { AuthPanel } from './auth-panel';

const health: HealthResponse = {
  status: 'healthy',
  service: 'gswguard-api',
  version: '0.1.0',
  checked_at: new Date().toISOString(),
  request_id: '00000000-0000-0000-0000-000000000000',
};

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <span className="brand-mark">YG</span>
        <span className="brand-name">YorGuard</span>
        <span className="environment">Prototype foundation</span>
      </header>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Golden Stone Works</p>
        <h1 id="page-title">Endpoint management, with a clear view of device health.</h1>
        <p className="lede">
          The dashboard foundation is online. Device enrollment, inventory, policy, and actions will
          be added through the approved implementation phases.
        </p>
        <div className="status-card" role="status">
          <span className="status-dot" aria-hidden="true" />
          <div>
            <strong>API contract healthy</strong>
            <p>
              {health.service} · v{health.version}
            </p>
          </div>
        </div>
        <AuthPanel />
      </section>
      <footer>YorGuard foundation · secure-by-design endpoint management</footer>
    </main>
  );
}
