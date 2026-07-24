-- GSWGuard Phase 4 normalized inventory and software history.

create table public.inventory_snapshots (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_id uuid not null references public.devices(id) on delete cascade,
  captured_at timestamptz not null,
  payload_hash text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique (device_id, payload_hash)
);

create table public.software_inventory (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_id uuid not null references public.devices(id) on delete cascade,
  software_key text not null,
  display_name text not null check (length(trim(display_name)) between 1 and 240),
  publisher text,
  version text not null check (length(trim(version)) between 1 and 80),
  architecture text,
  install_source text,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  is_present boolean not null default true,
  updated_at timestamptz not null default now(),
  unique (device_id, software_key)
);

create table public.software_change_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_id uuid not null references public.devices(id) on delete cascade,
  software_key text not null,
  change_type text not null check (change_type in ('added', 'removed', 'version_changed')),
  previous_version text,
  current_version text,
  detected_at timestamptz not null,
  correlation_id uuid,
  created_at timestamptz not null default now()
);

create index inventory_snapshots_device_captured_idx on public.inventory_snapshots(device_id, captured_at desc);
create index software_change_events_device_detected_idx on public.software_change_events(device_id, detected_at desc);

alter table public.inventory_snapshots enable row level security;
alter table public.software_inventory enable row level security;
alter table public.software_change_events enable row level security;

create policy inventory_member_read on public.inventory_snapshots
  for select using (public.is_org_member(organization_id));
create policy software_member_read on public.software_inventory
  for select using (public.is_org_member(organization_id));
create policy software_changes_member_read on public.software_change_events
  for select using (public.is_org_member(organization_id));

-- Agent writes are performed through a server-side device-authenticated adapter;
-- end-user JWT clients receive read-only access through these policies.
