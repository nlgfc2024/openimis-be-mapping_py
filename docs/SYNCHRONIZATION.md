# Synchronization contract and rollout

## Existing features reused

| Concern | CoreMIS feature |
| --- | --- |
| District selection | Published `location.MwDistrictPicker`; pass its UUID |
| Authentication and role grants | Core user, capability registry and Roles Management |
| Async mutation tracking | Core `OpenIMISMutation` / `BaseMutation` |
| Worker scheduling and progress | Core `run_as_scheduled_job`, `AsyncJob`, `ProgressReporter` |
| Staging, retries and recovery | `MsrEtlSyncUnit` and the existing MSR ETL sweeper |
| District access | Existing location district-assignment policy |
| References and verified memberships | Existing transactional location writer |

No parallel filter component, job system or reference store is introduced.
Frontend synchronization controls will reuse these contracts in the next chunk.

## MSR transport

The mapping provider uses GET `/api/v3/geo-locations` for districts and selected
district administrative locations/catchments. Detail refresh uses the deployed
v3 detail path. Verified membership continues to use the established
`/api/v2/micro-catchments/{id}/villages` endpoint. Membership is never inferred
from polygons or manually selected GVHs.

Pagination is bounded and restricted to the same origin and endpoint path.
Metadata requests use backend-held Bearer credentials and reject redirects.
Complete district snapshots include parents before children and a successful
membership response for every micro-catchment, including authoritative empty
responses. A failed page aborts staging; it cannot clear verified membership.

## GraphQL

Use the existing core mutation correlation convention. For example:

```graphql
mutation Start($input: MappingStartSyncMutationInput!) {
  mappingStartSync(input: $input) { clientMutationId }
}
```

```json
{
  "input": {
    "sourceInstance": "msr-malawi",
    "districtUuid": "UUID_RETURNED_BY_EXISTING_DISTRICT_PICKER",
    "clientMutationId": "UNIQUE_REQUEST_ID"
  }
}
```

Alternatively supply `districtMsrId: 13`. If both are supplied they must identify
the same reviewed district link. CoreMIS UUID, MSR ID and district code remain
separate identities. Missing or ambiguous reviewed links reject UUID resolution.

Poll the host mutation log for validation/scheduling failures, then poll the job:

```graphql
query Progress($request: String!) {
  mappingSyncRun(clientMutationId: $request) {
    id status total processed metrics error createdAt startedAt finishedAt
  }
}
```

`jobUuid` is also supported; supply exactly one identifier. A null job can mean
scheduling has not completed; it is not proof of success. Ordinary synchronizers
see their own jobs. Mapping managers may inspect another operator's job within
their permitted source/district scope. Read access alone cannot start a job.

## Ordering, retries and rollback

A stage receipt records source identity, policy, job/unit identity and a keyed
configuration fingerprint before downloading. It contains neither credentials
nor signed URLs. The existing staging sequence orders snapshots, not publication
revision alone. Both the new mapping entry point and legacy geographic import
use the same source/district transaction lock and writer.

A unit older than the last accepted unit is permanently rejected. Replaying the
same accepted unit is idempotent. Configuration/credential changes, revoked
rights or revoked district scope require a newly authorized snapshot. Writer or
membership failure rolls back references, memberships and ordering state
atomically. Transient failures use existing bounded retries and orphan recovery.
Old geographic staging rows without receipts are rejected and must be restaged.

MappingSyncState records only the last accepted unit and successful sync time.
Do not reset staging sequences independently of this state. All participating
workers must run the updated code; stop old workers before rolling out the
coordinator so they cannot bypass its lock.

## Rollout and rollback

1. Deploy mapping and MSR ETL updates together in editable local repositories.
2. Stop old workers; apply `mapping.0001_source_district_sync_state`.
3. Run portable tests and the disposable-schema host tests.
4. Configure the non-exposed mapping source and explicit district scope; use the
   legacy source alias to preserve backend credentials. Grant only needed roles.
5. Restart backend/workers and exercise one authorized district sync. Verify the
   existing reviewed MTANTHO link survives. New frontend activation is a separate
   chunk; the current pilot remains available.

To stop new mapping requests, disable its configuration and frontend contribution.
Retain the coordination table while either updated sync entry point is active.
A complete code rollback requires stopping workers and reviewing pending staging
units first. Do not drop the table while new workers are running. No rollback
requires deleting reference records, reviewed links, projects or payroll data.

The first live milestone is not complete coverage evidence: MTANTHO's prior MSR
verified membership response was empty. Manual CoreMIS GVH assignments remain
separate from source-verified coverage.
