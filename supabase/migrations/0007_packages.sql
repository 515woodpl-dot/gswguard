-- GSWGuard Phase 8 approved package catalog.

create table public.packages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  package_key text not null,
  version text not null check (length(trim(version)) between 1 and 80),
  format text not null check (format in ('winget', 'msi', 'exe', 'zip')),
  drive_file_id text,
  drive_shared_drive_id text,
  expected_sha256 text not null check (expected_sha256 ~ '^[0-9a-fA-F]{64}$'),
  expected_size_bytes bigint check (expected_size_bytes is null or expected_size_bytes >= 0),
  manifest jsonb not null,
  signature_required boolean not null default true,
  approved boolean not null default false,
  created_by uuid references auth.users(id) on delete set null,
  approved_by uuid references auth.users(id) on delete set null,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, package_key, version)
);

create index packages_approved_lookup_idx on public.packages(organization_id, package_key, version)
  where approved = true;

alter table public.packages enable row level security;

create policy packages_member_read on public.packages
  for select using (public.is_org_member(organization_id));
create policy packages_admin_mutate on public.packages
  for all using (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]))
  with check (public.has_org_role(organization_id, array['owner', 'administrator']::public.app_role[]));

-- Drive IDs and credentials are metadata/secret boundaries. Credentials never
-- enter this table; they remain in server deployment secret configuration.
