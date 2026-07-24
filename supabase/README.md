# Supabase foundation

Phase 2 migrations establish the organization/profile/membership model, role enum, one-time bootstrap state, append-only audit table, helper functions, and RLS policies. Every tenant-owned record introduced later must carry `organization_id` and use the same server-side authorization boundary.

Apply migrations through the Supabase CLI or the approved deployment pipeline. The local environment currently has no `supabase` CLI, PostgreSQL client, or running Docker database, so the pgTAP file is prepared for Supabase CI/manual execution but was not executed locally.
