# MSR import ownership and independent Mapping

Meeting direction: CoreMIS Mapping displays geography available to CoreMIS;
`msr_etl` owns the existing MSR import. This refactor supersedes the earlier
provider/synchronization ownership described in Chunks 2–4a.

## Dependency direction

```text
MSR APIs and private files
    → msr_etl provider / staging / coordinator
    → existing location references and verified memberships
    → local GeographicFeature / GeographicMembership publications
    → Mapping authorized read queries
    → dashboard and project Boundary map
```

Other importers/local CoreMIS processes may publish into the same geographic
store. Mapping neither imports `msr_etl` nor requests MSR. Conversely `msr_etl`
neither imports nor requires the Mapping package. Core continues to own identity,
role grants, jobs and progress reporting.

## Import behavior

The MSR provider/collector and configuration fingerprint/permission checks now
live in `msr_etl`. V3 location and detail requests, the established v2 village
membership endpoint and private signed-file delivery remain unchanged. Geometry
is downloaded/validated during staging, before database write locks. URLs and
credentials are not staged. Successful metadata/memberships use the existing
location writer; display publications mirror its accepted records in the same
transaction. Geometry files remain bounded/checksummed/sanitized.

`MsrGeoSyncState` owns source/district serialization and accepted stage-unit
ordering. Its migration adopts the old physical state without a dependency on
the Mapping app. Mapping's historical state table is retained as an archive for
controlled rollback; no active writer uses it. Old v1 receipts are rejected for
restaging. The new importer uses v2 `_msr_geo` receipts and existing MSR rights.

Geometry failure retains the last accepted local geometry, while refresh status
reports the failure. Metadata/geometry revision races cannot replace accepted
geometry. A confirmed withdrawal clears it. Subsequent accepted publication can
restore it. Mapping refresh is a local read even when the source is offline.

## Deployment sequence

1. Finish current imports and stop all old workers/backend processes. Deploy all
   affected feature-branch repositories together; rebuild mapping/MSR frontend.
2. Run `python manage.py migrate --plan`, then `python manage.py migrate`.
3. Preview/apply the one-time configuration transfer:

   ```bash
   python manage.py migrate_geo_ownership
   python manage.py migrate_geo_ownership --apply
   ```

   This moves any Mapping-held source overrides into non-exposed MSR ETL
   configuration, converts display district IDs to CoreMIS UUID scopes, removes
   frontend source/sync settings and configures the existing import screen to
   reuse the published district picker. It grants no roles and changes no links.
4. Seed accepted geography from existing imported records and retrieve published
   files once while MSR is reachable:

   ```bash
   python manage.py materialize_msr_geography --source-type msr_geo_v3 --district-id 13 --download
   ```

   This does not reimport/reparent locations or change reviewed matches. A
   successful geometry seed is required for offline display because the previous
   implementation retrieved geometry transiently and did not persist its bytes.
5. Restart updated backend/workers and reload the frontend session. MSR imports
   use the existing Import Data - Filters Location tab. Users need existing MSR
   query/execute rights; old Mapping sync grants are not automatically converted.
6. Verify 66 MTANTHO memberships, original reviewed link/project context, local
   geometry and a repeat import with MSR's standard mutation. Disable/block source
   access when checking Mapping's read-only behavior.

## Rollback

Stop workers before rollback. Keep geographic data and reviewed links. The
coordinator migration reverse copies the highest accepted ordering back into the
legacy state table when present. Do not restart old workers against the archived
state without this transfer. New-format pending snapshots need deliberate
restaging when switching versions. Retain backend configuration backups before
rolling back source/UUID-scope configuration. No project/payroll data deletion is
part of either deployment direction.

## Acceptance limits

The previous pilot confirmed 66 IDs against the SQL export and CoreMIS membership,
repeat synchronization without duplicates and the shared project map. This
refactor must preserve those records. Backend tests cover source-neutral local
reads, scoped direct IDs, offline geometry, real concurrent importers, state
handover/reverse and replacement/withdrawal/restoration/failure behavior.

The CoreMIS adapter remains specific to the selected nlgfc2024 host. A second
upstream openIMIS host, beneficiary GPS feeds, basemap/point layers and a full
browser lifecycle demonstration remain separate work. Deprecated MSR-named read
fields are compatibility aliases over local provenance; the current frontend uses
source-neutral fields. Historical numeric reference IDs are never silently
reinterpreted as different publication IDs.

## Validation completed — 23 November 2026

- Mapping portable schema/access/import-boundary tests: 14 passed.
- MSR provider/import-ownership tests: 9 passed.
- Isolated PostgreSQL integration tests: 100 passed, including real worker
  serialization, configuration/permission checks, migration forward/reverse,
  geometry replacement/withdrawal/restoration, last-good retention, direct-ID
  scope checks and a source-neutral non-MSR publication.
- Frontend Mapping module/geometry and host React component checks passed.
- Existing MSR frontend test files passed, including schema-change cleanup that
  removes stale numeric filters while preserving household location filters.
- Django system checks and migration drift checks passed.
- Mapping/MSR frontend package builds and the full CoreMIS frontend assembly
  compiled successfully using the host's existing disabled-ESLint-plugin setup.

Local migration/configuration handover and geometry seeding were applied. The
preflight found no active import jobs. Original references remained at 3,560;
MTANTHO's reference remained 3523 and its reviewed micro-catchment link remained 3.
The local store contains 3,560 geographic features and 25 accepted geometries.
The 66 MTANTHO coverage IDs match the original verified membership rows exactly.

The composed live Mapping API returned Dedza/MTANTHO geometry and all 66 coverage
IDs with MSR source configuration disabled and HTTP requests blocked **in the
verification process only**. No MSR service was stopped. A historical numeric
reference ID still resolved to MTANTHO rather than a different publication.

A live MSR ETL import then ran through the existing core worker executor with
Mapping disabled **in that process only**: job
`90b714c5-b851-46f3-9495-f705378c928c` completed SUCCESS, 3,560/3,560 records. It
preserved the reference count, reviewed link and all 66 memberships. The worker
was invoked directly to avoid adding a duplicate task to any old scheduler; this
is backend execution evidence, not a claim of a new authenticated browser test.

Restart all long-lived backend/workers and reload the frontend before using the
new import screen. The SVG project map continues through the shared component.
Full browser acceptance after restart remains to be confirmed by the operator.
