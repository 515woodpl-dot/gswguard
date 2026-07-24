# Scaling assumptions and traffic estimates

These are planning estimates, not measured capacity commitments. Assumptions: one API instance, REST polling, 30-second job polling, five-minute heartbeats, six-hour full inventory, 15-minute software scans, jitter, no overlapping scans, and roughly 1 KiB heartbeat, 5 KiB job poll, 50 KiB software scan, and 250 KiB compressed full inventory payload per device.

| Fleet | Poll requests/day | Heartbeats/day | Software scans/day | Full inventories/day | Approx. API requests/day |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 devices | 5,760 | 576 | 192 | 8 | ~6,536 |
| 10 devices | 28,800 | 2,880 | 960 | 40 | ~32,680 |
| 50 devices | 144,000 | 14,400 | 4,800 | 200 | ~163,400 |

Approximate routine payload egress is 2–5 MiB/day, 10–25 MiB/day, and 50–125 MiB/day respectively, excluding package downloads. Package traffic is the sum of approved package sizes and retries and is expected to dominate bandwidth. Audit/timeline growth depends on inventory-diff and job volume; normalize snapshots and retain only meaningful changes. Notification volume is event-driven, with offline alerts after 24 hours and deduplication.

At two to ten devices, a small DigitalOcean App Platform API and Supabase project should be evaluated against request/time and database limits during Phase 11. At fifty devices, measure database polling, add indexes/retention jobs, and reassess a queue worker or Redis; do not introduce it prematurely.
