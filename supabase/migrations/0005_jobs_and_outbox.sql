-- GSWGuard Phase 6 durable jobs and transactional event outbox.

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_id uuid not null references public.devices(id) on delete cascade,
  action_type text not null check (action_type in (
    'refresh_inventory', 'lock_screen', 'restart', 'install_software',
    'uninstall_software', 'windows_update', 'defender_quick_scan', 'remediation'
  )),
  action_version integer not null default 1 check (action_version > 0),
  action_payload jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users(id) on delete set null,
  confirmation_at timestamptz,
  reason text check (reason is null or length(trim(reason)) between 1 and 500),
  idempotency_key text not null check (length(trim(idempotency_key)) between 8 and 160),
  expires_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'claimed', 'running', 'succeeded', 'failed', 'expired', 'cancelled')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  claimed_at timestamptz,
  claim_expires_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  result jsonb,
  error_code text,
  retry_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, device_id, idempotency_key)
);

create table public.event_outbox (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  event_type text not null,
  aggregate_type text not null,
  aggregate_id uuid not null,
  payload jsonb not null,
  available_at timestamptz not null default now(),
  attempts integer not null default 0 check (attempts >= 0),
  processed_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);

create index jobs_device_poll_idx on public.jobs(device_id, status, expires_at, created_at)
  where status in ('pending', 'claimed');
create index outbox_pending_idx on public.event_outbox(available_at, created_at)
  where processed_at is null;

alter table public.jobs enable row level security;
alter table public.event_outbox enable row level security;

create policy jobs_member_read on public.jobs
  for select using (public.is_org_member(organization_id));
create policy jobs_admin_create on public.jobs
  for insert with check (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));
create policy jobs_admin_cancel on public.jobs
  for update using (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));
create policy outbox_owner_read on public.event_outbox
  for select using (public.has_org_role(organization_id, array['owner']::public.app_role[]));

-- Device polling and outbox workers use a server-side adapter. Claims must use
-- a short transaction with row locking and a lease, equivalent to:
-- SELECT ... FOR UPDATE SKIP LOCKED, then UPDATE status='claimed'.
