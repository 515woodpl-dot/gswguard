-- GSWGuard Phase 2 security foundation.
-- Apply through Supabase migrations; do not run against an unrelated database.

create extension if not exists pgcrypto;

create type public.app_role as enum ('owner', 'administrator', 'viewer');

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(trim(name)) between 1 and 160),
  created_at timestamptz not null default now()
);

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text check (display_name is null or length(display_name) <= 160),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_memberships (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.app_role not null,
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table public.bootstrap_state (
  id boolean primary key default true check (id),
  organization_id uuid references public.organizations(id) on delete restrict,
  completed_at timestamptz,
  completed_by uuid references auth.users(id) on delete restrict,
  constraint bootstrap_completed_together check ((completed_at is null) = (completed_by is null))
);

insert into public.bootstrap_state (id) values (true) on conflict (id) do nothing;

create table public.audit_log (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_type text not null check (actor_type in ('user', 'device', 'system')),
  action text not null check (length(trim(action)) between 1 and 120),
  target_type text check (target_type is null or length(target_type) <= 80),
  target_id uuid,
  correlation_id uuid,
  outcome text not null check (outcome in ('accepted', 'succeeded', 'failed', 'denied')),
  reason text check (reason is null or length(reason) <= 500),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index organization_memberships_user_idx on public.organization_memberships(user_id);
create index audit_log_organization_created_idx on public.audit_log(organization_id, created_at desc);

create or replace function public.is_org_member(target_org uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.organization_memberships m
    where m.organization_id = target_org and m.user_id = auth.uid()
  );
$$;

create or replace function public.has_org_role(target_org uuid, allowed_roles public.app_role[])
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.organization_memberships m
    where m.organization_id = target_org
      and m.user_id = auth.uid()
      and m.role = any(allowed_roles)
  );
$$;

alter table public.organizations enable row level security;
alter table public.profiles enable row level security;
alter table public.organization_memberships enable row level security;
alter table public.bootstrap_state enable row level security;
alter table public.audit_log enable row level security;

create policy organizations_member_read on public.organizations
  for select using (public.is_org_member(id));

create policy profiles_self_read on public.profiles
  for select using (user_id = auth.uid());

create policy memberships_self_or_owner_read on public.organization_memberships
  for select using (
    user_id = auth.uid()
    or public.has_org_role(organization_id, array['owner']::public.app_role[])
  );

create policy audit_member_read on public.audit_log
  for select using (public.is_org_member(organization_id));

-- No client role may read bootstrap state or write audit rows directly.
-- Server-side bootstrap/audit functions will be added with tightly scoped
-- SECURITY DEFINER permissions when the Supabase integration is wired.

create or replace function public.prevent_audit_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'audit_log is append-only';
end;
$$;

create trigger audit_log_immutable
before update or delete on public.audit_log
for each row execute function public.prevent_audit_mutation();
