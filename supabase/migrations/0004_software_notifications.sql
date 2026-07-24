-- GSWGuard Phase 5 software-change notifications.

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  device_id uuid references public.devices(id) on delete cascade,
  software_change_event_id uuid references public.software_change_events(id) on delete set null,
  channel text not null check (channel in ('dashboard', 'email')),
  notification_key text not null,
  title text not null check (length(trim(title)) between 1 and 160),
  body text not null check (length(trim(body)) between 1 and 1000),
  status text not null check (status in ('pending', 'sent', 'failed', 'suppressed')),
  sent_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  unique (channel, notification_key)
);

create index notifications_organization_created_idx on public.notifications(organization_id, created_at desc);
create index notifications_pending_idx on public.notifications(status, created_at)
  where status = 'pending';

alter table public.notifications enable row level security;

create policy notifications_member_read on public.notifications
  for select using (public.is_org_member(organization_id));

-- Notification writes and provider delivery are server-side operations.
