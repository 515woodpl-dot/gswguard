-- GSWGuard Phase 10 audit integrity, export, and retention metadata.

alter table public.audit_log add column if not exists previous_hash text;
alter table public.audit_log add column if not exists event_hash text;

create table public.retention_policies (
  organization_id uuid primary key references public.organizations(id) on delete cascade,
  audit_days integer not null default 365 check (audit_days between 30 and 3650),
  inventory_days integer not null default 90 check (inventory_days between 7 and 730),
  notification_days integer not null default 90 check (notification_days between 7 and 730),
  updated_at timestamptz not null default now()
);

create table public.audit_exports (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  requested_by uuid references auth.users(id) on delete set null,
  format text not null check (format in ('csv', 'xlsx', 'pdf')),
  filters jsonb not null default '{}'::jsonb,
  status text not null check (status in ('requested', 'completed', 'failed', 'expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index audit_log_hash_idx on public.audit_log(organization_id, created_at, event_hash);

alter table public.retention_policies enable row level security;
alter table public.audit_exports enable row level security;

create policy retention_owner_read on public.retention_policies
  for select using (public.has_org_role(organization_id, array['owner']::public.app_role[]));
create policy audit_exports_owner_read on public.audit_exports
  for select using (public.has_org_role(organization_id, array['owner']::public.app_role[]));
