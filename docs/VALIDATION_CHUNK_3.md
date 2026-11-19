# Chunk 3 validation — 19 November 2026

Target: the existing nlgfc2024 CoreMIS backend assembly recorded in BASELINE.md,
with locally editable mapping and MSR ETL repositories. Upstream openIMIS is not
a separately verified host profile.

| Check | Result |
| --- | --- |
| Portable read/provider tests | 18 passed |
| Isolated PostgreSQL host tests | 85 passed |
| Two workers, same source/district | Writes serialized; newer state accepted after older transaction |
| Older unit after newer accepted snapshot | Rejected before calling writer |
| Repeat accepted unit | Idempotent; writer called once |
| Membership failure | Ordering state rolled back; legacy tests verify reference rollback |
| Config/credential rotation and revoked scope | Rejected; checks repeated after lock |
| Core scheduling | Queued only after transaction commit |
| Legacy jobs, staging and sweeper | Passed; includes new mapping completion/stale-job cases |
| Django system checks | No issues |
| Mapping migration drift | No changes detected |
| Local migration | `mapping.0001_source_district_sync_state` applied |
| Composed GraphQL schema | New mutation, progress query and districtUuid input registered |
| Existing district picker identity | CoreMIS district UUID resolves to MSR district ID 13 |
| Existing credential alias | Provider validates without fetching or copying credentials |
| Existing pilot read checks | Dedza hierarchy/pagination and reviewed MTANTHO link preserved; reference count unchanged |

Host tests create and remove a uniquely named schema containing temporary state,
reference, membership, staging and job tables. An existing CoreMIS user is read
only to satisfy job foreign keys. No test writes geographic records to public
application tables. The schema cleanup executes even when checks fail.

The shared sweeper tests initially encountered the host's stricter password
policy in their old user fixture. The fixture now supplies a compliant test
password; the isolated host runner reuses an existing actor instead of creating
application users. The final host suite passed.

This chunk does **not** claim a live synchronization through the newly enabled
mapping API, frontend menu/project cutover, complete MSR village coverage, or GPS
overlays. The new mapping configuration remains disabled by default; activation
and role grants follow the documented rollout. Existing pilot access remains.

Rollback and worker deployment requirements are in SYNCHRONIZATION.md. Deploy
both backend repository commits together; restart all workers so an older
worker cannot bypass the new source/district coordinator.
