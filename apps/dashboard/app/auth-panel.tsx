'use client';

import { createClient, type Session } from '@supabase/supabase-js';
import { useEffect, useState } from 'react';
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
  status: string;
  last_heartbeat_at: string | null;
};

export function AuthPanel() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [apiUser, setApiUser] = useState<ApiUser | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [deviceError, setDeviceError] = useState<string | null>(null);
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

  useEffect(() => {
    if (!config || !session || !apiUser) return;
    void fetch(`${config.apiBaseUrl}/api/v1/devices`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Device inventory failed (${response.status})`);
        return (await response.json()) as DeviceSummary[];
      })
      .then(setDevices)
      .catch((error: unknown) => setDeviceError(error instanceof Error ? error.message : 'Unable to load devices'));
  }, [apiUser, config, session]);

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

  if (session && apiUser) {
    return (
      <>
        <div className="auth-panel" role="status">
          <div>
            <strong>{apiUser.email ?? session.user.email}</strong>
            <p>{apiUser.role ?? 'authenticated'} · API session verified</p>
          </div>
          <button type="button" className="secondary-button" onClick={signOut}>
            Sign out
          </button>
        </div>
        <section className="device-panel" aria-labelledby="device-heading">
          <div className="device-panel-heading">
            <div>
              <strong id="device-heading">Devices</strong>
              <p>{devices.length} enrolled device{devices.length === 1 ? '' : 's'}</p>
            </div>
            <span className="device-count">{devices.filter((device) => device.status === 'online').length} online</span>
          </div>
          {deviceError ? <p className="auth-error">{deviceError}</p> : null}
          {devices.length === 0 && !deviceError ? <p className="empty-state">No devices enrolled yet. Create an enrollment token to add the first endpoint.</p> : null}
          {devices.length > 0 ? (
            <div className="device-list">
              {devices.map((device) => (
                <div className="device-row" key={device.id}>
                  <div>
                    <strong>{device.device_name}</strong>
                    <p>{[device.manufacturer, device.model].filter(Boolean).join(' · ') || 'Windows endpoint'} · Agent {device.agent_version}</p>
                  </div>
                  <span className={`device-status ${device.status}`}>{device.status}</span>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </>
    );
  }

  return (
    <form className="auth-panel auth-form" onSubmit={submit}>
      <div>
        <strong>Sign in to GSWGuard</strong>
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
