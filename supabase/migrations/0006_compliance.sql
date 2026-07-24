-- GSWGuard Phase 7 compliance policies and evaluation history.

create table public.compliance_policies (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  policy_key text not null,
  name text not null check (length(trim(name)) between 1 and 160),
  rule_type text not null,
  configuration jsonb not null default '{}'::jsonb,
  enabled boolean not null default true,
  automatic_remediation boolean not null default false,
  weight integer not null default 1 check (weight between 1 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, policy_key)
);

create table public.compliance_evaluations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  device_id uuid not null references public.devices(id) on delete cascade,
  score numeric(5,2) not null check (score between 0 and 100),
  evaluated_at timestamptz not null,
  evidence_hash text not null,
  created_at timestamptz not null default now()
);

create table public.compliance_results (
  id uuid primary key default gen_random_uuid(),
  evaluation_id uuid not null references public.compliance_evaluations(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  device_id uuid not null references public.devices(id) on delete cascade,
  policy_id uuid not null references public.compliance_policies(id) on delete cascade,
  passed boolean not null,
  evidence jsonb not null default '{}'::jsonb,
  reason text not null check (length(trim(reason)) between 1 and 500),
  created_at timestamptz not null default now()
);

create table public.remediation_attempts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  device_id uuid not null references public.devices(id) on delete cascade,
  policy_id uuid not null references public.compliance_policies(id) on delete cascade,
  evidence_hash text not null,
  job_id uuid references public.jobs(id) on delete set null,
  attempted_at timestamptz not null default now(),
  outcome text not null check (outcome in ('submitted', 'suppressed', 'succeeded', 'failed'))
);

create index compliance_evaluations_device_idx on public.compliance_evaluations(device_id, evaluated_at desc);
create index compliance_results_device_idx on public.compliance_results(device_id, created_at desc);
create index remediation_attempts_lookup_idx on public.remediation_attempts(device_id, policy_id, evidence_hash);

alter table public.compliance_policies enable row level security;
alter table public.compliance_evaluations enable row level security;
alter table public.compliance_results enable row level security;
alter table public.remediation_attempts enable row level security;

create policy compliance_policies_member_read on public.compliance_policies
  for select using (public.is_org_member(organization_id));
create policy compliance_policies_admin_mutate on public.compliance_policies
  for all using (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]))
  with check (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));
create policy compliance_evaluations_member_read on public.compliance_evaluations
  for select using (public.is_org_member(organization_id));
create policy compliance_results_member_read on public.compliance_results
  for select using (public.is_org_member(organization_id));
create policy remediation_member_read on public.remediation_attempts
  for select using (public.is_org_member(organization_id));
