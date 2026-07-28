'use client';

import { createClient, type Session } from '@supabase/supabase-js';
import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

type RuntimeConfig = {
  supabaseUrl: string;
  supabaseAnonKey: string;
  apiBaseUrl: string;
};

type ApiUser = {
  user_id: string;
  email: string | null;
  role: string | null;
  organization_id: string | null;
};

type DeviceSummary = {
  id: string;
  device_name: string;
  manufacturer: string | null;
  model: string | null;
  agent_version: string;
  platform: string;
  os_version: string | null;
  status: string;
  last_heartbeat_at: string | null;
};

export function AuthPanel() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [apiUser, setApiUser] = useState<ApiUser | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [devicesLoaded, setDevicesLoaded] = useState(false);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [platformFilter, setPlatformFilter] = useState('all');
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [enrollmentToken, setEnrollmentToken] = useState<string | null>(null);
  const [enrollmentTokenExpires, setEnrollmentTokenExpires] = useState<string | null>(null);
  const [tokenBusy, setTokenBusy] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('Loading sign-in…');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch('/api/runtime-config', { cache: 'no-store' })
      .then((response) => response.json() as Promise<RuntimeConfig>)
      .then((runtimeConfig) => {
        if (!active) return;
        setConfig(runtimeConfig);
        if (!runtimeConfig.supabaseUrl || !runtimeConfig.supabaseAnonKey) {
          setMessage('Supabase sign-in is not configured.');
          return;
        }
        const supabase = createClient(runtimeConfig.supabaseUrl, runtimeConfig.supabaseAnonKey);
        void supabase.auth.getSession().then(({ data }) => {
          if (!active) return;
          setSession(data.session);
          setMessage(data.session ? 'Signed in.' : 'Sign in to continue.');
        });
        const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
          if (!active) return;
          setSession(nextSession);
          setMessage(nextSession ? 'Signed in.' : 'Sign in to continue.');
        });
        return () => listener.subscription.unsubscribe();
      })
      .catch(() => setMessage('Unable to load sign-in configuration.'));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!config || !session) return;
    void fetch(`${config.apiBaseUrl}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(body?.detail ?? `API authentication failed (${response.status})`);
        }
        return (await response.json()) as ApiUser;
      })
      .then((user) => {
        setApiUser(user);
        setMessage('Signed in and API session verified.');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'API authentication failed');
        setMessage('Supabase session is valid, but API authentication failed.');
      });
  }, [config, session]);

  const loadDevices = useCallback(async (showBusy = false) => {
    if (!config || !session || !apiUser) return;
    if (showBusy) setRefreshBusy(true);
    setDeviceError(null);
    setDevicesLoaded(false);
    await fetch(`${config.apiBaseUrl}/api/v1/devices`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Device inventory failed (${response.status})`);
        return (await response.json()) as DeviceSummary[];
      })
      .then(setDevices)
      .catch((error: unknown) => setDeviceError(error instanceof Error ? error.message : 'Unable to load devices'))
      .finally(() => {
        setDevicesLoaded(true);
        setRefreshBusy(false);
      });
  }, [apiUser, config, session]);

  useEffect(() => {
    // Inventory is an external API resource; load it when the verified session changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDevices();
  }, [loadDevices]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config) {
      setMessage('Sign-in configuration is still loading. Try again in a moment.');
      return;
    }
    setBusy(true);
    setMessage('Signing in…');
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    try {
      const result = await Promise.race([
        supabase.auth.signInWithPassword({ email, password }),
        new Promise<never>((_, reject) =>
          window.setTimeout(() => reject(new Error('Sign-in request timed out. Check the Pi network connection.')), 15000),
        ),
      ]);
      if (result.error) setMessage(result.error.message);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Unable to complete sign-in.');
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (!config) return;
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    await supabase.auth.signOut();
    setApiUser(null);
  }

  async function createEnrollmentToken() {
    if (!config || !session) return;
    setTokenBusy(true);
    setEnrollmentToken(null);
    setEnrollmentTokenExpires(null);
    setDeviceError(null);
    try {
      const response = await fetch(`${config.apiBaseUrl}/api/v1/enrollment-tokens`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ label: 'YorGuard endpoint', ttl_minutes: 60 }),
      });
      const body = (await response.json()) as { token?: string; expires_at?: string; detail?: string };
      if (!response.ok || !body.token) throw new Error(body.detail ?? `Token creation failed (${response.status})`);
      setEnrollmentToken(body.token);
      setEnrollmentTokenExpires(body.expires_at ? new Date(body.expires_at).toLocaleString() : null);
    } catch (error: unknown) {
      setDeviceError(error instanceof Error ? error.message : 'Unable to create enrollment token');
    } finally {
      setTokenBusy(false);
    }
  }

  async function copyEnrollmentToken() {
    if (!enrollmentToken) return;
    try {
      await navigator.clipboard.writeText(enrollmentToken);
      setCopyMessage('Token copied');
      window.setTimeout(() => setCopyMessage(null), 2000);
    } catch {
      setCopyMessage('Copy unavailable — select the token manually');
    }
  }

  if (session && apiUser) {
    const onlineCount = devices.filter((device) => device.status === 'online').length;
    const attentionCount = devices.filter((device) => device.status !== 'online').length;
    const platformCount = new Set(devices.map((device) => device.platform)).size;
    const platforms = Array.from(new Set(devices.map((device) => device.platform))).sort();
    const visibleDevices = platformFilter === 'all' ? devices : devices.filter((device) => device.platform === platformFilter);
    return (
      <>
        <div className="workspace-header" id="overview">
          <div>
            <p className="eyebrow">YorGuard control center</p>
            <h2>Fleet overview</h2>
            <p>Monitor endpoint health, enrollment, and platform coverage from one workspace.</p>
          </div>
          <nav className="workspace-nav" aria-label="Dashboard sections">
            <a className="active" href="#overview">Overview</a>
            <a href="#devices">Devices</a>
            <span aria-disabled="true" title="Activity view is not enabled yet">Activity</span>
            <span aria-disabled="true" title="Policy view is not enabled yet">Policies</span>
          </nav>
        </div>
        <div className="auth-panel session-panel" role="status">
          <div>
            <strong>{apiUser.email ?? session.user.email}</strong>
            <p>{apiUser.role ?? 'authenticated'} · API session verified</p>
          </div>
          <button type="button" className="secondary-button" onClick={signOut}>
            Sign out
          </button>
        </div>
        <div className="metric-grid">
          <div className="metric-card"><span>Total devices</span><strong>{devices.length}</strong><small>Enrolled endpoints</small></div>
          <div className="metric-card metric-good"><span>Online now</span><strong>{onlineCount}</strong><small>Reporting normally</small></div>
          <div className="metric-card metric-attention"><span>Needs attention</span><strong>{attentionCount}</strong><small>Offline or revoked</small></div>
          <div className="metric-card"><span>Platforms</span><strong>{platformCount}</strong><small>Across the fleet</small></div>
        </div>
        <section className="device-panel" id="devices" aria-labelledby="device-heading">
          <div className="device-panel-heading">
            <div>
              <strong id="device-heading">Devices</strong>
              <p>{devices.length} enrolled device{devices.length === 1 ? '' : 's'}</p>
            </div>
            <div className="device-actions">
              <span className="device-count">{devices.filter((device) => device.status === 'online').length} online</span>
              <button type="button" className="secondary-button" onClick={() => void loadDevices(true)} disabled={refreshBusy}>
                {refreshBusy ? 'Refreshing…' : 'Refresh'}
              </button>
              {apiUser.role === 'owner' || apiUser.role === 'administrator' ? (
                <button type="button" onClick={createEnrollmentToken} disabled={tokenBusy}>
                  {tokenBusy ? 'Creating…' : 'Create enrollment token'}
                </button>
              ) : null}
            </div>
          </div>
          {deviceError ? <p className="auth-error">{deviceError}</p> : null}
          {enrollmentToken ? (
            <div className="token-result" role="status">
              <strong>Copy this one-time token to the endpoint installer:</strong>
              <code>{enrollmentToken}</code>
              {enrollmentTokenExpires ? <span>Expires {enrollmentTokenExpires}</span> : null}
              <button type="button" className="secondary-button token-copy" onClick={() => void copyEnrollmentToken()}>
                {copyMessage ?? 'Copy token'}
              </button>
            </div>
          ) : null}
          {!devicesLoaded ? <p className="empty-state">Loading device inventory…</p> : null}
          {devicesLoaded && devices.length === 0 && !deviceError ? <p className="empty-state">No devices enrolled yet. Create an enrollment token to add the first endpoint.</p> : null}
          {devices.length > 0 ? (
            <>
              <div className="device-toolbar">
                <label>
                  Platform
                  <select value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)}>
                    <option value="all">All platforms</option>
                    {platforms.map((platform) => <option key={platform} value={platform}>{platform}</option>)}
                  </select>
                </label>
                <span>{visibleDevices.length} shown</span>
              </div>
            <div className="device-list">
              {visibleDevices.map((device) => (
                <div className="device-row" key={device.id}>
                  <div>
                    <strong>{device.device_name}</strong>
                    <p>{device.platform} · {[device.manufacturer, device.model].filter(Boolean).join(' · ') || 'Endpoint'} · Agent {device.agent_version}</p>
                  </div>
                  <span className={`device-status ${device.status}`}>{device.status}</span>
                </div>
              ))}
            </div>
            </>
          ) : null}
        </section>
      </>
    );
  }

  return (
    <form className="auth-panel auth-form" onSubmit={submit}>
      <div>
        <strong>Sign in to YorGuard</strong>
        <p>{message}</p>
        {session && apiError ? <p className="auth-error">Backend response: {apiError}</p> : null}
      </div>
      <label>
        Email
        <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      <label>
        Password
        <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
}
