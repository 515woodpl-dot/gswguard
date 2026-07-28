-- Store device actors separately from human Supabase users.

alter table public.audit_log
  add column if not exists actor_device_id uuid references public.devices(id) on delete set null;

create index if not exists audit_log_device_actor_idx
  on public.audit_log(actor_device_id, created_at desc)
  where actor_device_id is not null;
