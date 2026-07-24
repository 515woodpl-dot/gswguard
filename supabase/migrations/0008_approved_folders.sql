-- GSWGuard Phase 9 approved-folder metadata and operation audit.

create table public.approved_folders (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (length(trim(name)) between 1 and 160),
  provider text not null check (provider in ('google_drive', 'local_test')),
  provider_root_id text not null,
  allowed_extensions text[] not null default '{}',
  max_file_size_bytes bigint not null default 104857600 check (max_file_size_bytes between 1 and 10737418240),
  allow_upload boolean not null default true,
  allow_download boolean not null default true,
  allow_delete boolean not null default false,
  quarantine_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, name)
);

create table public.file_objects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  folder_id uuid not null references public.approved_folders(id) on delete cascade,
  relative_path text not null,
  provider_object_id text,
  provider_version text,
  size_bytes bigint not null check (size_bytes >= 0),
  sha256 text check (sha256 is null or sha256 ~ '^[0-9a-fA-F]{64}$'),
  status text not null default 'active' check (status in ('active', 'quarantined', 'deleted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (folder_id, relative_path)
);

create table public.file_operations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  folder_id uuid not null references public.approved_folders(id) on delete restrict,
  file_object_id uuid references public.file_objects(id) on delete set null,
  operation text not null check (operation in ('upload', 'download', 'quarantine', 'delete')),
  actor_user_id uuid references auth.users(id) on delete set null,
  device_id uuid references public.devices(id) on delete set null,
  reason text check (reason is null or length(trim(reason)) between 1 and 500),
  size_bytes bigint,
  outcome text not null check (outcome in ('started', 'succeeded', 'failed', 'denied')),
  error_code text,
  created_at timestamptz not null default now()
);

create index file_objects_folder_status_idx on public.file_objects(folder_id, status);
create index file_operations_organization_created_idx on public.file_operations(organization_id, created_at desc);

alter table public.approved_folders enable row level security;
alter table public.file_objects enable row level security;
alter table public.file_operations enable row level security;

create policy approved_folders_member_read on public.approved_folders
  for select using (public.is_org_member(organization_id));
create policy approved_folders_owner_mutate on public.approved_folders
  for all using (public.has_org_role(organization_id, array['owner']::public.app_role[]))
  with check (public.has_org_role(organization_id, array['owner']::public.app_role[]));
create policy file_objects_member_read on public.file_objects
  for select using (public.is_org_member(organization_id));
create policy file_operations_member_read on public.file_operations
  for select using (public.is_org_member(organization_id));

-- File bytes and mutation writes are handled by a server-side provider adapter.
