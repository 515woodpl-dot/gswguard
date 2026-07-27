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

export function AuthPanel() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [apiUser, setApiUser] = useState<ApiUser | null>(null);
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
        if (!response.ok) throw new Error('API authentication failed');
        return (await response.json()) as ApiUser;
      })
      .then(setApiUser)
      .catch(() => setMessage('Supabase session is valid, but API authentication failed.'));
  }, [config, session]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config) {
      setMessage('Sign-in configuration is still loading. Try again in a moment.');
      return;
    }
    setBusy(true);
    setMessage('Signing in…');
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) setMessage(error.message);
  }

  async function signOut() {
    if (!config) return;
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    await supabase.auth.signOut();
    setApiUser(null);
  }

  if (session && apiUser) {
    return (
      <div className="auth-panel" role="status">
        <div>
          <strong>{apiUser.email ?? session.user.email}</strong>
          <p>{apiUser.role ?? 'authenticated'} · API session verified</p>
        </div>
        <button type="button" className="secondary-button" onClick={signOut}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <form className="auth-panel auth-form" onSubmit={submit}>
      <div>
        <strong>Sign in to GSWGuard</strong>
        <p>{message}</p>
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
