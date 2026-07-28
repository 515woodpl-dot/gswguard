-- YorGuard cross-platform device metadata.

alter table public.devices
  add column platform text not null default 'windows',
  add column os_version text;

alter table public.devices
  add constraint devices_platform_check
  check (platform in ('windows', 'macos', 'ios', 'ipados', 'android', 'linux', 'unknown'));

create index devices_organization_platform_idx on public.devices(organization_id, platform);
