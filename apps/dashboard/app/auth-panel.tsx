'use client';

import { createClient, type Session } from '@supabase/supabase-js';
import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

type RuntimeConfig = {
  supabaseUrl: string;
  supabaseAnonKey: string;
  apiBaseUrl: string;
  // Immutable release ref (tag or commit SHA) the Windows bootstrap pins the
  // installer to. Falls back to a known tag when unset.
  agentReleaseRef?: string;
  agentSigningPublicKeyXmlBase64?: string;
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
  serial_number: string | null;
  agent_version: string;
  platform: string;
  os_version: string | null;
  status: string;
  last_heartbeat_at: string | null;
};

type JobSummary = {
  id: string;
  device_id: string;
  action_type: string;
  status: string;
  created_at: string;
  expires_at: string;
  attempt_count: number;
  error_code?: string | null;
};

type PolicySummary = {
  id: string;
  policy_key: string;
  name: string;
  rule_type: string;
  expected_value: string;
  enabled: boolean;
  automatic_remediation: boolean;
  weight: number;
};

type ComplianceEvaluation = {
  device_id: string;
  // null when no policy produced usable evidence for this device, which is not
  // the same as a measured 0%.
  score: number | null;
  evaluated_at: string;
  results: Array<{ passed: boolean; outcome: 'passed' | 'failed' | 'unknown'; reason: string }>;
  unknown_count: number;
};

// Report what was actually measured. The agents currently report placeholder
// values for most of the security posture, so a device can legitimately have
// policies configured and still have nothing to score.
function formatCompliance(evaluation: ComplianceEvaluation | undefined): string {
  if (!evaluation) return 'Not evaluated';
  if (evaluation.score === null) {
    return evaluation.results.length === 0 ? 'No policies' : 'Awaiting evidence';
  }
  const unknown = evaluation.unknown_count > 0 ? ` · ${evaluation.unknown_count} awaiting evidence` : '';
  return `${evaluation.score}%${unknown}`;
}

type WorkspaceView = 'overview' | 'devices' | 'policies' | 'activity';

const policyRuleLabels: Record<string, string> = {
  bitlocker: 'BitLocker encryption',
  firewall: 'Firewall',
  defender: 'Defender health',
  secure_boot: 'Secure Boot',
  tpm: 'TPM',
  automatic_updates: 'Automatic updates',
  windows_edition: 'Windows edition',
};

const policyExpectedOptions: Record<string, string[]> = {
  bitlocker: ['on', 'off'],
  firewall: ['on', 'off'],
  defender: ['healthy', 'unhealthy'],
  secure_boot: ['on', 'off'],
  tpm: ['present', 'missing'],
  automatic_updates: ['on', 'off'],
  windows_edition: ['Pro', 'Enterprise', 'Education'],
};

type InventorySummary = {
  device_id: string;
  captured_at: string;
  snapshot: {
    platform?: string;
    os_version?: string;
    manufacturer?: string;
    model?: string;
    serial_number?: string;
    cpu?: { name?: string; logical_processors?: number };
    installed_ram_bytes?: number;
    security?: { bitlocker?: string; firewall?: string; defender?: string; secure_boot?: string; tpm?: string; automatic_updates?: string };
    storage?: Array<{ name?: string; capacity_bytes?: number; free_bytes?: number }>;
    network_adapters?: Array<{ name?: string; ip_addresses?: string[] }>;
    local_accounts?: Array<{ name?: string; account_type?: string; is_administrator?: boolean }>;
    software?: unknown[];
  };
};

export function AuthPanel() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [apiUser, setApiUser] = useState<ApiUser | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [latestInventory, setLatestInventory] = useState<InventorySummary[]>([]);
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
  const [jobError, setJobError] = useState<string | null>(null);
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [policyBusy, setPolicyBusy] = useState(false);
  const [policyName, setPolicyName] = useState('Firewall enabled');
  const [policyRuleType, setPolicyRuleType] = useState('firewall');
  const [policyExpectedValue, setPolicyExpectedValue] = useState('on');
  const [complianceEvaluations, setComplianceEvaluations] = useState<ComplianceEvaluation[]>([]);
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<WorkspaceView>('overview');

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

  const loadLatestInventory = useCallback(async () => {
    if (!config || !session || !apiUser) return;
    setDeviceError(null);
    await fetch(`${config.apiBaseUrl}/api/v1/inventory/latest`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Latest inventory failed (${response.status})`);
        return (await response.json()) as InventorySummary[];
      })
      .then(setLatestInventory)
      .catch((error: unknown) => setDeviceError(error instanceof Error ? error.message : 'Unable to load latest inventory. Try Refresh again.'));
  }, [apiUser, config, session]);

  useEffect(() => {
    // Latest inventory is an external API resource loaded after authentication.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadLatestInventory();
  }, [loadLatestInventory]);

  const loadJobs = useCallback(async () => {
    if (!config || !session || !apiUser) return;
    setJobError(null);
    await fetch(`${config.apiBaseUrl}/api/v1/jobs`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Job history failed (${response.status})`);
        return (await response.json()) as JobSummary[];
      })
      .then(setJobs)
      .catch((error: unknown) => setJobError(error instanceof Error ? error.message : 'Unable to load jobs. Try Refresh jobs again.'));
  }, [apiUser, config, session]);

  useEffect(() => {
    // Job history is an external API resource loaded after authentication.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadJobs();
  }, [loadJobs]);

  const loadPolicies = useCallback(async () => {
    if (!config || !session || !apiUser) return;
    setPolicyError(null);
    await fetch(`${config.apiBaseUrl}/api/v1/compliance/policies`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Policy load failed (${response.status})`);
        return (await response.json()) as PolicySummary[];
      })
      .then(setPolicies)
      .catch((error: unknown) => setPolicyError(error instanceof Error ? error.message : 'Unable to load policies'));
  }, [apiUser, config, session]);

  useEffect(() => {
    // Policy configuration is an external API resource loaded after authentication.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadPolicies();
  }, [loadPolicies]);

  async function createPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config || !session) return;
    setPolicyBusy(true);
    setPolicyError(null);
    try {
      const generatedPolicyKey = `${policyName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}-${policyRuleType}`;
      const response = await fetch(`${config.apiBaseUrl}/api/v1/compliance/policies`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          policy_key: generatedPolicyKey,
          name: policyName,
          rule_type: policyRuleType,
          expected_value: policyExpectedValue,
          enabled: true,
          automatic_remediation: false,
          weight: 1,
        }),
      });
      const body = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(body?.detail ?? `Policy creation failed (${response.status})`);
      await loadPolicies();
      setPolicyModalOpen(false);
    } catch (error: unknown) {
      setPolicyError(error instanceof Error ? error.message : 'Unable to create policy');
    } finally {
      setPolicyBusy(false);
    }
  }

  const loadCompliance = useCallback(async () => {
    if (!config || !session || !apiUser) return;
    await fetch(`${config.apiBaseUrl}/api/v1/compliance/latest`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Compliance evaluation failed (${response.status})`);
        return (await response.json()) as ComplianceEvaluation[];
      })
      .then(setComplianceEvaluations)
      .catch(() => setComplianceEvaluations([]));
  }, [apiUser, config, session]);

  useEffect(() => {
    void loadCompliance();
  }, [loadCompliance]);

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
        body: JSON.stringify({ label: 'YorGuard endpoint', ttl_minutes: 15 }),
      });
      const body = (await response.json()) as { token?: string; expires_at?: string; detail?: string };
      if (!response.ok || !body.token) throw new Error(body.detail ?? `Token creation failed (${response.status})`);
      setEnrollmentToken(body.token);
      setEnrollmentTokenExpires(body.expires_at ? new Date(body.expires_at).toLocaleString() : null);
      setTokenModalOpen(true);
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

  function downloadWindowsBootstrap() {
    if (!enrollmentToken || !config) return;
    // Pin the bootstrap to an immutable signed release ref, so the fetched
    // installer is exactly the reviewed release and cannot change underneath an
    // enrolling machine. The installer verifies the package again before use.
    const installerRef = config.agentReleaseRef;
    const signingKey = config.agentSigningPublicKeyXmlBase64;
    if (!installerRef || !signingKey) {
      setDeviceError('Signed Windows bootstrap is not configured yet.');
      return;
    }
    const releaseBase = 'https://github.com/515woodpl-dot/gswguard/releases/download/' + installerRef;
    const packageUrl = releaseBase + '/yorguard-windows-agent.zip';
    const versionUrl = releaseBase + '/version.txt';
    const manifestUrl = releaseBase + '/manifest.txt';
    const signatureUrl = releaseBase + '/manifest.sig';
    const encode = (value: string) => btoa(value);
    // The bootstrap embeds a single-use enrollment token, so it deletes both the
    // downloaded installer and itself after running to avoid leaving the token
    // in the downloads folder / TEMP.
    const script = [
      '# YorGuard Windows bootstrap - run PowerShell as Administrator',
      '# Contains a single-use enrollment token; it self-deletes after running.',
      '$ErrorActionPreference = "Stop"',
      '$releaseRef = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("' + encode(installerRef) + '"))',
      '$apiBaseUrl = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("' + encode(config.apiBaseUrl) + '"))',
      '$enrollmentToken = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("' + encode(enrollmentToken) + '"))',
      '$publicKeyXml = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("' + signingKey + '"))',
      'if ($apiBaseUrl -notmatch "^https://") { throw "YorGuard API must use HTTPS." }',
      'if ([string]::IsNullOrWhiteSpace($publicKeyXml)) { throw "YorGuard signing key is not configured." }',
      '$releaseBase = "https://github.com/515woodpl-dot/gswguard/releases/download/" + $releaseRef',
      '$packageUrl = "$releaseBase/yorguard-windows-agent.zip"',
      '$versionUrl = "$releaseBase/version.txt"',
      '$manifestUrl = "$releaseBase/manifest.txt"',
      '$signatureUrl = "$releaseBase/manifest.sig"',
      '$root = Join-Path $env:TEMP ("yorguard-bootstrap-" + [guid]::NewGuid().ToString("N"))',
      '$package = Join-Path $root "yorguard-windows-agent.zip"',
      '$manifest = Join-Path $root "manifest.txt"',
      '$signature = Join-Path $root "manifest.sig"',
      '$extract = Join-Path $root "extract"',
      'New-Item -ItemType Directory -Force -Path $root | Out-Null',
      'try {',
      '  Invoke-WebRequest -Uri $packageUrl -OutFile $package -UseBasicParsing',
      '  Invoke-WebRequest -Uri $manifestUrl -OutFile $manifest -UseBasicParsing',
      '  Invoke-WebRequest -Uri $signatureUrl -OutFile $signature -UseBasicParsing',
      '  $manifestBytes = [IO.File]::ReadAllBytes($manifest)',
      '  $signatureBytes = [Convert]::FromBase64String((Get-Content -Raw $signature).Trim())',
      '  $rsa = New-Object Security.Cryptography.RSACryptoServiceProvider',
      '  $sha256 = New-Object Security.Cryptography.SHA256Managed',
      '  try {',
      '    $rsa.FromXmlString($publicKeyXml)',
      '    if (-not $rsa.VerifyData($manifestBytes, $sha256, $signatureBytes)) { throw "Package manifest signature is invalid." }',
      '  } finally { $sha256.Dispose(); $rsa.Dispose() }',
      '  $fields = @{}',
      '  foreach ($line in ([Text.Encoding]::ASCII.GetString($manifestBytes) -split "\\r?\\n")) { if ($line -match "^\\s*([^=]+)=(.*)$") { $fields[$matches[1].Trim()] = $matches[2].Trim() } }',
      '  if ($fields["version"] -ne $releaseRef) { throw "Signed release version does not match the pinned release ref." }',
      '  if ($fields["file"] -ne "yorguard-windows-agent.zip") { throw "Signed manifest names an unexpected package." }',
      '  $actualHash = (Get-FileHash $package -Algorithm SHA256).Hash.ToLower()',
      '  if ($actualHash -ne $fields["sha256"].ToLower()) { throw "Package hash does not match the signed manifest." }',
      '  Expand-Archive -Path $package -DestinationPath $extract -Force',
      '  $installer = Join-Path $extract "install-windows-agent.ps1"',
      '  if (-not (Test-Path $installer)) { throw "Signed package does not contain the installer." }',
      '  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -ApiBaseUrl $apiBaseUrl -EnrollmentToken $enrollmentToken -PackageUrl $packageUrl -VersionUrl $versionUrl -ManifestUrl $manifestUrl -SignatureUrl $signatureUrl -PackagePath $package -ManifestPath $manifest -SignaturePath $signature',
      '  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }',
      '} finally {',
      '  Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue',
      '  if ($PSCommandPath) { Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue }',
      '}',
      '',
    ].join('\n');
    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'install-yorguard-windows.ps1';
    link.click();
    URL.revokeObjectURL(url);
  }

  if (session && apiUser) {
    const onlineCount = devices.filter((device) => device.status === 'online').length;
    const attentionCount = devices.filter((device) => device.status !== 'online').length;
    const platformCount = new Set(devices.map((device) => device.platform)).size;
    const platforms = Array.from(new Set(devices.map((device) => device.platform))).sort();
    const visibleDevices = platformFilter === 'all' ? devices : devices.filter((device) => device.platform === platformFilter);
    const latestJobs = Array.from(jobs.reduce((latest, job) => {
      const key = `${job.device_id}:${job.action_type}`;
      if (!latest.has(key)) latest.set(key, job);
      return latest;
    }, new Map<string, JobSummary>()).values());
    const viewCopy: Record<WorkspaceView, { title: string; description: string }> = {
      overview: { title: 'Fleet overview', description: 'A focused view of endpoint health and coverage.' },
      devices: { title: 'Devices', description: 'Inspect endpoint status, inventory, and reported health.' },
      policies: { title: 'Policies', description: 'Define observation rules against the latest endpoint inventory.' },
      activity: { title: 'Activity', description: 'Review endpoint jobs and their current state.' },
    };
    const currentView = viewCopy[activeView];
    // True when policies exist but no device produced evidence any of them could
    // score, so the Policies view can say so instead of implying 0% compliance.
    const awaitingEvidence =
      complianceEvaluations.length > 0 && complianceEvaluations.every((item) => item.score === null);
    return (
      <div className="app-frame">
        <aside className="side-panel" aria-label="Primary navigation">
          <div className="side-brand"><span className="brand-mark">YG</span><span>YorGuard</span></div>
          <div className="side-workspace"><span className="status-dot" aria-hidden="true" /><div><strong>Control center</strong><small>Connected</small></div></div>
          <nav className="side-nav">
            <button type="button" className={activeView === 'overview' ? 'active' : ''} onClick={() => setActiveView('overview')}><span>⌂</span>Overview</button>
            <button type="button" className={activeView === 'devices' ? 'active' : ''} onClick={() => setActiveView('devices')}><span>▣</span>Devices</button>
            <button type="button" className={activeView === 'policies' ? 'active' : ''} onClick={() => setActiveView('policies')}><span>✓</span>Policies</button>
            <button type="button" className={activeView === 'activity' ? 'active' : ''} onClick={() => setActiveView('activity')}><span>↗</span>Activity</button>
          </nav>
          <div className="side-footer"><div><strong>{apiUser.email ?? session.user.email}</strong><small>{apiUser.role ?? 'authenticated'} · Verified</small></div><button type="button" className="side-signout" onClick={signOut}>Sign out</button></div>
        </aside>
        <main className="app-content">
          <header className="page-header" id="overview">
            <div><p className="eyebrow">YorGuard control center</p><h1>{currentView.title}</h1><p>{currentView.description}</p></div>
            <div className="header-actions"><span className="api-pill"><span className="status-dot" aria-hidden="true" />API healthy</span>{apiUser.role === 'owner' || apiUser.role === 'administrator' ? <button type="button" onClick={() => void createEnrollmentToken()} disabled={tokenBusy}>{tokenBusy ? 'Creating…' : 'Add endpoint'}</button> : null}</div>
          </header>
        {activeView === 'overview' ? <>
        <div className="metric-grid">
          <div className="metric-card"><span>Total devices</span><strong>{devices.length}</strong><small>Enrolled endpoints</small></div>
          <div className="metric-card metric-good"><span>Online now</span><strong>{onlineCount}</strong><small>Reporting normally</small></div>
          <div className="metric-card metric-attention"><span>Needs attention</span><strong>{attentionCount}</strong><small>Offline or revoked</small></div>
          <div className="metric-card"><span>Platforms</span><strong>{platformCount}</strong><small>Across the fleet</small></div>
        </div>
        <div className="quick-grid">
          <button type="button" className="quick-card" onClick={() => setActiveView('devices')}><span>Devices</span><strong>{devices.length} enrolled</strong><small>Open endpoint inventory →</small></button>
          <button type="button" className="quick-card" onClick={() => setActiveView('policies')}><span>Policies</span><strong>{policies.length} configured</strong><small>Review compliance rules →</small></button>
          <button type="button" className="quick-card" onClick={() => setActiveView('activity')}><span>Activity</span><strong>{latestJobs.length} recent jobs</strong><small>Review endpoint activity →</small></button>
        </div>
        </> : null}
        {activeView === 'devices' ? <section className="device-panel" id="devices" aria-labelledby="device-heading">
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
                <div className="device-row device-row-clickable" key={device.id} role="button" tabIndex={0} onClick={() => setSelectedDeviceId(device.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelectedDeviceId(device.id); }}>
                  <div>
                    <strong>{device.device_name}</strong>
                    <p>{device.platform} · {[device.manufacturer, device.model].filter(Boolean).join(' · ') || 'Endpoint'} · Agent {device.agent_version}</p>
                    {device.status !== 'online' ? (
                      <small className="device-attention">
                        Attention: {device.status === 'revoked' ? 'Device revoked' : 'No recent heartbeat'}
                        {device.last_heartbeat_at ? ` · Last seen ${new Date(device.last_heartbeat_at).toLocaleString()}` : ' · Never reported a heartbeat'}
                      </small>
                    ) : null}
                    {(() => {
                      const inventory = latestInventory.find((item) => item.device_id === device.id);
                      if (!inventory) return <small>No inventory snapshot yet</small>;
                      const ramGb = inventory.snapshot.installed_ram_bytes ? Math.round(inventory.snapshot.installed_ram_bytes / 1024 ** 3) : null;
                      const compliance = complianceEvaluations.find((item) => item.device_id === device.id);
                      return <small>Inventory {new Date(inventory.captured_at).toLocaleString()} · {inventory.snapshot.cpu?.name ?? 'CPU'} · {ramGb ? `${ramGb} GB RAM` : 'RAM unavailable'} · {inventory.snapshot.software?.length ?? 0} apps{compliance ? ` · Compliance ${formatCompliance(compliance)}` : ''}</small>;
                    })()}
                  </div>
                  <span className={`device-status ${device.status}`}>{device.status}</span>
                </div>
              ))}
            </div>
            </>
          ) : null}
        </section> : null}
        {activeView === 'policies' ? <section className="device-panel policy-panel" id="policies" aria-labelledby="policy-heading">
            <div className="device-panel-heading">
            <div>
              <strong id="policy-heading">Policies</strong>
              <p>{policies.length} rule{policies.length === 1 ? '' : 's'} configured · evaluation only, no automatic changes</p>
            </div>
            <div className="device-actions">
              <button type="button" className="secondary-button" onClick={() => void loadPolicies()}>Refresh policies</button>
              {apiUser.role === 'owner' || apiUser.role === 'administrator' ? <button type="button" onClick={() => setPolicyModalOpen(true)}>Add policy</button> : null}
            </div>
          </div>
          {policyError ? <p className="auth-error">{policyError}</p> : null}
          {policies.length === 0 && !policyError ? <p className="empty-state">No compliance policies configured.</p> : null}
          {policies.length > 0 && awaitingEvidence ? (
            <p className="empty-state">
              These rules are configured but cannot be scored yet: the endpoint agents do not
              report the security fields they check, so every result is &ldquo;awaiting
              evidence&rdquo; rather than pass or fail.
            </p>
          ) : null}
          {policies.length > 0 ? (
            <div className="policy-list">
              {policies.map((policy) => (
                <div className="policy-row" key={policy.id}>
                  <div><strong>{policy.name}</strong><p>Check {policyRuleLabels[policy.rule_type] ?? policy.rule_type} · required state: <b>{policy.expected_value}</b> · weight {policy.weight}</p></div>
                  <span className="policy-mode">{policy.automatic_remediation ? 'Remediation enabled' : 'Observe only'}</span>
                </div>
              ))}
            </div>
          ) : null}
        </section> : null}
        {activeView === 'activity' ? <section className="device-panel job-panel" id="jobs" aria-labelledby="job-heading">
          <div className="device-panel-heading">
            <div>
              <strong id="job-heading">Job Center</strong>
              <p>Inventory reporting runs automatically in the endpoint receiver.</p>
            </div>
            <div className="device-actions">
              <button type="button" className="secondary-button" onClick={() => void loadJobs()}>Refresh jobs</button>
            </div>
          </div>
          {jobError ? <p className="auth-error">{jobError}</p> : null}
          {latestJobs.length === 0 ? <p className="empty-state">No endpoint jobs recorded.</p> : (
            <div className="job-list">
              {latestJobs.map((job) => (
                <div className="job-row" key={job.id}>
                  <div><strong>{job.action_type}</strong><p>{job.device_id} · {new Date(job.created_at).toLocaleString()}</p></div>
                  <span className={`device-status ${job.status}`}>{job.status}</span>
                </div>
              ))}
            </div>
          )}
        </section> : null}
        {selectedDeviceId ? (() => {
          const selectedDevice = devices.find((device) => device.id === selectedDeviceId);
          const inventory = latestInventory.find((item) => item.device_id === selectedDeviceId);
          if (!selectedDevice) return null;
          const snapshot = inventory?.snapshot;
          const ramGb = snapshot?.installed_ram_bytes ? Math.round(snapshot.installed_ram_bytes / 1024 ** 3) : null;
          const compliance = complianceEvaluations.find((item) => item.device_id === selectedDeviceId);
          return (
            <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedDeviceId(null)}>
              <section className="modal-card inventory-modal" role="dialog" aria-modal="true" aria-labelledby="inventory-modal-title" onMouseDown={(event) => event.stopPropagation()}>
                <div className="modal-heading"><div><p className="eyebrow">Device details</p><h2 id="inventory-modal-title">{selectedDevice.device_name}</h2><p className="modal-copy">{selectedDevice.platform} · {selectedDevice.status} · Agent {selectedDevice.agent_version}</p></div><button type="button" className="modal-close" onClick={() => setSelectedDeviceId(null)} aria-label="Close">×</button></div>
                {!snapshot ? <p className="empty-state">No inventory snapshot has been reported by this device yet.</p> : (
                  <>
                    <div className="detail-card-grid">
                      <div><span>Hardware</span><strong>{snapshot.manufacturer ?? selectedDevice.manufacturer ?? 'Unknown'} {snapshot.model ?? selectedDevice.model ?? ''}</strong></div>
                      <div><span>Operating system</span><strong>{snapshot.os_version ?? selectedDevice.os_version ?? 'Unknown'}</strong></div>
                      <div><span>Processor</span><strong>{snapshot.cpu?.name ?? 'Unknown'}{snapshot.cpu?.logical_processors ? ` · ${snapshot.cpu.logical_processors} cores` : ''}</strong></div>
                      <div><span>Memory</span><strong>{ramGb ? `${ramGb} GB RAM` : 'Unknown'}</strong></div>
                      <div><span>Serial number</span><strong>{snapshot.serial_number ?? selectedDevice.serial_number ?? 'Unavailable'}</strong></div>
                      <div><span>Compliance</span><strong>{formatCompliance(compliance)}</strong></div>
                    </div>
                    <div className="detail-section"><h3>Security posture</h3><div className="detail-chip-grid">{Object.entries(snapshot.security ?? {}).map(([key, value]) => <span className="detail-chip" key={key}><b>{key.replaceAll('_', ' ')}</b>{String(value)}</span>)}</div></div>
                    <div className="detail-section"><h3>Storage and software</h3><p>{snapshot.storage?.length ?? 0} storage devices · {snapshot.software?.length ?? 0} installed applications</p></div>
                    <div className="detail-section"><h3>Network and accounts</h3><p>{snapshot.network_adapters?.length ?? 0} network adapters · {snapshot.local_accounts?.length ?? 0} local accounts</p></div>
                  </>
                )}
              </section>
            </div>
          );
        })() : null}
        {tokenModalOpen && enrollmentToken ? (
          <div className="modal-backdrop" role="presentation" onMouseDown={() => setTokenModalOpen(false)}>
            <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="token-modal-title" onMouseDown={(event) => event.stopPropagation()}>
              <div className="modal-heading"><div><p className="eyebrow">Endpoint enrollment</p><h2 id="token-modal-title">Connect a device</h2></div><button type="button" className="modal-close" onClick={() => setTokenModalOpen(false)} aria-label="Close">×</button></div>
              <p className="modal-copy">Use this one-time token in the endpoint installer. It expires {enrollmentTokenExpires ?? 'soon'}.</p>
              <div className="token-result" role="status"><code>{enrollmentToken}</code><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => void copyEnrollmentToken()}>{copyMessage ?? 'Copy token'}</button><button type="button" onClick={downloadWindowsBootstrap}>Download Windows bootstrap</button></div></div>
            </section>
          </div>
        ) : null}
        {policyModalOpen ? (
          <div className="modal-backdrop" role="presentation" onMouseDown={() => setPolicyModalOpen(false)}>
            <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="policy-modal-title" onMouseDown={(event) => event.stopPropagation()}>
              <div className="modal-heading"><div><p className="eyebrow">Compliance</p><h2 id="policy-modal-title">Add a policy</h2></div><button type="button" className="modal-close" onClick={() => setPolicyModalOpen(false)} aria-label="Close">×</button></div>
              <p className="modal-copy">Policies start in observation-only mode. No remediation action will be submitted.</p>
              <form className="modal-form" onSubmit={createPolicy}>
                <label>Policy name<input value={policyName} onChange={(event) => setPolicyName(event.target.value)} required /></label>
                <label>What should be checked<select value={policyRuleType} onChange={(event) => { const nextRule = event.target.value; setPolicyRuleType(nextRule); setPolicyExpectedValue(policyExpectedOptions[nextRule][0]); }}><option value="bitlocker">BitLocker encryption</option><option value="firewall">Firewall</option><option value="defender">Defender health</option><option value="secure_boot">Secure Boot</option><option value="tpm">TPM</option><option value="automatic_updates">Automatic updates</option><option value="windows_edition">Windows edition</option></select></label>
                <label>Required state<select value={policyExpectedValue} onChange={(event) => setPolicyExpectedValue(event.target.value)} required>{policyExpectedOptions[policyRuleType].map((option) => <option key={option} value={option}>{option[0].toUpperCase() + option.slice(1)}</option>)}</select></label>
                <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setPolicyModalOpen(false)}>Cancel</button><button type="submit" disabled={policyBusy}>{policyBusy ? 'Adding…' : 'Add policy'}</button></div>
              </form>
            </section>
          </div>
        ) : null}
        </main>
      </div>
    );
  }

  return (
    <div className="auth-frame">
      <aside className="auth-side"><div className="side-brand"><span className="brand-mark">YG</span><span>YorGuard</span></div><div className="auth-side-copy"><p className="eyebrow">Endpoint operations</p><h1>See what matters across every device.</h1><p>Secure enrollment, device health, and policy visibility in one focused workspace.</p></div><div className="side-health"><span className="status-dot" aria-hidden="true" /><div><strong>API contract healthy</strong><small>YorGuard service · v0.1.0</small></div></div></aside>
      <section className="auth-content">
        <div className="auth-content-heading"><span className="quiet-label">YorGuard control center</span><span className="secure-label">Private workspace</span></div>
        <form className="login-card" onSubmit={submit}>
          <div><p className="eyebrow">Welcome back</p><h2>Sign in to YorGuard</h2><p className="login-copy">{message}</p>{session && apiError ? <p className="auth-error">Backend response: {apiError}</p> : null}</div>
          <label>Email<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
      </section>
    </div>
  );
}
