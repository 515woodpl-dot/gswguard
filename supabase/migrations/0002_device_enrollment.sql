-- GSWGuard Phase 3 enrollment and device identity.

create type public.device_status as enum ('enrolling', 'online', 'offline', 'revoked');

create table public.devices (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_name text not null check (length(trim(device_name)) between 1 and 160),
  manufacturer text,
  model text,
  serial_number text,
  agent_version text not null check (length(trim(agent_version)) between 1 and 40),
  credential_hash text not null unique,
  credential_created_at timestamptz not null default now(),
  credential_rotated_at timestamptz,
  status public.device_status not null default 'enrolling',
  enrolled_at timestamptz not null default now(),
  last_heartbeat_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, serial_number)
);

create table public.enrollment_tokens (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  token_hash text not null unique,
  label text check (label is null or length(trim(label)) <= 120),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  consumed_device_id uuid references public.devices(id) on delete restrict,
  constraint token_consumption_together check ((consumed_at is null) = (consumed_device_id is null)),
  constraint token_expiry_after_creation check (expires_at > created_at)
);

create index devices_organization_status_idx on public.devices(organization_id, status);
create index devices_last_heartbeat_idx on public.devices(last_heartbeat_at);
create index enrollment_tokens_active_idx on public.enrollment_tokens(organization_id, expires_at)
  where consumed_at is null;

alter table public.devices enable row level security;
alter table public.enrollment_tokens enable row level security;

create policy devices_member_read on public.devices
  for select using (public.is_org_member(organization_id));

create policy devices_admin_mutate on public.devices
  for all using (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]))
  with check (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));

create policy enrollment_tokens_admin_read on public.enrollment_tokens
  for select using (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));

-- Token consumption must be performed by a server-side transaction using the
-- hashed token and a row lock. The plaintext token is never stored or returned
-- by PostgreSQL. Agent credential authentication uses a separate server-side
-- adapter and never relies on Supabase human-user JWTs.
